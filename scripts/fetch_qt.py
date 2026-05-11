"""
주만나 QT 크롤러 (로컬 실행용)
====================================
오륜교회 주만나 페이지에서 오늘의 QT를 가져와 JSON으로 저장합니다.

사용법:
    # 기본 실행 (data/qt/YYYY-MM-DD.json 에 저장)
    python scripts/fetch_qt.py

    # 드라이런 (저장하지 않고 출력만)
    python scripts/fetch_qt.py --dry-run

    # 저장 경로 지정
    python scripts/fetch_qt.py --output data/qt/custom.json

참고:
- 오륜교회 서버는 특정 User-Agent/IP를 차단할 수 있습니다.
- 403 에러 발생 시: VPN 끄기, 다른 네트워크에서 시도.
- GitHub Actions 환경에서는 정상 동작합니다.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# ===== 설정 =====
URL = "https://oryun.org/life/?menu=248"
MAIN_URL = "https://oryun.org/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

KST = timezone(timedelta(hours=9))
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "qt"


# ===== 로깅 =====
def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now(KST).strftime("%H:%M:%S")
    prefix = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌"}.get(level, "• ")
    print(f"[{now}] {prefix} {msg}")


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


# ===== HTTP =====
def fetch_page(retries: int = 3) -> str:
    """페이지 HTML을 가져온다. 실패 시 재시도."""
    session = requests.Session()
    session.headers.update(HEADERS)

    # 메인 페이지 선방문 (쿠키/세션 획득)
    log("메인 페이지 방문 중...")
    try:
        session.get(MAIN_URL, timeout=30)
    except requests.RequestException as e:
        log(f"메인 페이지 접근 실패 (무시하고 계속): {e}", "WARN")

    # QT 페이지 요청 (재시도 포함)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            log(f"QT 페이지 요청 중 (시도 {attempt}/{retries})...")
            res = session.get(URL, timeout=30)
            res.raise_for_status()
            res.encoding = "utf-8"
            log(f"응답 수신 완료 ({len(res.text):,} bytes)", "OK")
            return res.text
        except requests.RequestException as e:
            last_err = e
            log(f"시도 {attempt} 실패: {e}", "WARN")
            if attempt < retries:
                wait = 2 ** attempt
                log(f"{wait}초 후 재시도...")
                time.sleep(wait)

    raise RuntimeError(f"페이지 요청이 {retries}회 모두 실패했습니다: {last_err}")


# ===== 파싱 =====
# 오륜교회 페이지는 절 범위 구분 기호로 보통 하이픈(-)을 쓰지만,
# 가끔 엔대시(–)·엠대시(—)·물결(~) 등 다른 문자가 섞여 들어온다.
# 정규식이 이런 변형을 못 알아보면 제목·구절 파싱이 통째로 실패하므로,
# 파싱 전에 모든 대시류를 평범한 하이픈으로 정규화한다.
_DASH_VARIANTS = "‐‑‒–—―−⁃⁓∼〜～－~"
_DASH_TRANS = {ord(ch): "-" for ch in _DASH_VARIANTS}


def _normalize_dashes(s: str) -> str:
    """범위 구분 기호로 쓰일 수 있는 모든 대시·물결류를 '-' 하나로 통일."""
    return s.translate(_DASH_TRANS)


def split_title_and_ref(line: str) -> tuple:
    """'회복으로 나아가라 룻기 1:15-22' → ('회복으로 나아가라', '룻기 1:15-22')

    장을 넘나드는 범위('사무엘상 6:19-7:2')도 인식한다.
    """
    line = _normalize_dashes(line.strip())
    pattern = r"^(.+?)\s+([가-힣]+(?:상|하)?)\s+(\d+):(\d+[a-z]?)(?:-(?:(\d+):)?(\d+[a-z]?))?$"
    m = re.match(pattern, line)
    if not m:
        log(f"제목/구절 파싱 실패: {line}", "WARN")
        return line, ""

    title = m.group(1).strip()
    book = m.group(2)
    chapter = m.group(3)
    v_start = m.group(4)
    end_ch = m.group(5)
    v_end = m.group(6)

    ref = f"{book} {chapter}:{v_start}"
    if v_end:
        ref += f"-{end_ch}:{v_end}" if end_ch else f"-{v_end}"
    return title, ref


def parse_scripture_ref(ref: str) -> dict:
    """'룻기 1:15-22' → {book, chapter, start, end, ...}

    장을 넘나드는 범위('사무엘상 6:19-7:2')도 처리한다.
    - chapter / start / end: 하위 호환용 (start_chapter, start_verse, end_verse)
    - start_chapter, start_verse, end_chapter, end_verse: 정확한 범위
    - cross_chapter: 시작 장과 끝 장이 다르면 True
    """
    empty = {
        "book": "", "chapter": 0, "start": 0, "end": 0,
        "start_chapter": 0, "start_verse": 0, "end_chapter": 0, "end_verse": 0,
        "cross_chapter": False,
    }
    m = re.match(
        r"([가-힣]+(?:상|하)?)\s+(\d+):(\d+[a-z]?)(?:-(?:(\d+):)?(\d+[a-z]?))?",
        _normalize_dashes(ref),
    )
    if not m:
        return empty

    def _num(raw: str) -> int:
        return int(re.sub(r"[^\d]", "", raw))

    book = m.group(1)
    start_chapter = int(m.group(2))
    start_verse = _num(m.group(3))
    end_chapter = int(m.group(4)) if m.group(4) else start_chapter
    end_verse = _num(m.group(5)) if m.group(5) else start_verse

    return {
        "book": book,
        "chapter": start_chapter,
        "start": start_verse,
        "end": end_verse,
        "start_chapter": start_chapter,
        "start_verse": start_verse,
        "end_chapter": end_chapter,
        "end_verse": end_verse,
        "cross_chapter": end_chapter != start_chapter,
    }


def extract_verses(soup: BeautifulSoup, ref: dict) -> list:
    """
    구절 추출. 한글 본문만.
    한글 본문 뒤에 '-' 구분선 후 영문이 나오므로 구분선 이후는 스킵.

    장을 넘나드는 범위(예: 사무엘상 6:19-7:2)도 처리한다. 페이지에는 절 번호가
    6:19→19, 7:1→1 처럼 장이 바뀔 때 다시 작아지므로, 절 번호가 직전보다 작아지면
    다음 장으로 넘어간 것으로 본다. cross_chapter인 경우 각 절에 chapter도 기록한다.
    """
    cross = ref.get("cross_chapter", False)
    start_ch = ref.get("start_chapter") or ref.get("chapter") or 0
    start_v = ref.get("start_verse") or ref.get("start") or 0
    end_ch = ref.get("end_chapter") or ref.get("chapter") or 0
    end_v = ref.get("end_verse") or ref.get("end") or 0

    verses = []
    seen = set()          # (chapter, number) 중복 방지
    korean_done = False
    cur_ch = start_ch
    prev_num = None

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)

        # 영문 구분선 감지
        if text in {"-", "--", "—"}:
            korean_done = True
            continue
        if korean_done:
            continue

        # 절 번호로 시작?
        m = re.match(r"^(\d+)\s+(.+)$", text)
        if not m:
            continue

        verse_num = int(m.group(1))
        verse_text = m.group(2).strip()

        # 한글 없으면 스킵 (영문 배제)
        if not re.search(r"[가-힣]", verse_text):
            continue

        # 장 경계 감지: 번호가 직전보다 작아지면 다음 장
        if cross and prev_num is not None and verse_num <= prev_num and cur_ch < end_ch:
            cur_ch += 1
        prev_num = verse_num

        # 범위 밖 (장·절 함께 비교)
        if (cur_ch, verse_num) < (start_ch, start_v):
            continue
        if (cur_ch, verse_num) > (end_ch, end_v):
            continue

        key = (cur_ch, verse_num)
        if key in seen:
            continue
        seen.add(key)

        verse = {"number": verse_num, "text": verse_text}
        if cross:
            verse["chapter"] = cur_ch
        verses.append(verse)

    if not cross:
        verses.sort(key=lambda v: v["number"])
    return verses


def extract_questions(soup: BeautifulSoup) -> list:
    """'오늘의 만나' 질문 추출"""
    questions = []
    for elem in soup.find_all(["dt", "dd", "p"]):
        text = elem.get_text(" ", strip=True)
        if "오늘의 만나" in text:
            parts = text.split("오늘의 만나", 1)
            if len(parts) == 2 and parts[1].strip():
                q = parts[1].strip()
                q = re.sub(r"\s*\d+\s*/\s*\d+\s*$", "", q).strip()
                q = re.sub(r"\s*(등록|취소)\s*$", "", q).strip()
                if q and q not in questions and len(q) > 5:
                    questions.append(q)
    return questions


def parse_qt(html: str) -> dict:
    """HTML → QT 데이터 dict"""
    # lxml 우선, 없으면 내장 html.parser로 fallback (Python 3.14 호환성)
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # 날짜 레이블
    date_label = None
    title_line = None
    for dt in soup.find_all("dt"):
        text = dt.get_text(strip=True)
        if re.match(r"^\d{2}\.\d{2}", text):
            date_label = text
            dd = dt.find_next_sibling("dd")
            if dd:
                # " " separator로 HTML <br>/블록 경계에 공백 보존
                title_line = dd.get_text(" ", strip=True)
                # 연속 공백 하나로 압축
                title_line = re.sub(r"\s+", " ", title_line).strip()
            break

    if not date_label:
        raise ValueError("날짜 레이블을 찾을 수 없습니다. 페이지 구조가 바뀌었을 수 있어요.")
    log(f"날짜 레이블: {date_label}", "OK")

    if not title_line:
        raise ValueError("제목 라인을 찾을 수 없습니다.")

    title, scripture_ref = split_title_and_ref(title_line)
    log(f"제목: {title}", "OK")
    log(f"구절: {scripture_ref}", "OK")

    ref_parsed = parse_scripture_ref(scripture_ref)

    # 부제
    subtitle = ""
    all_lis = soup.find_all("li")
    verse_lis = [li for li in all_lis if re.match(r"^\d+\s", li.get_text(strip=True))]
    if verse_lis:
        first_verse = verse_lis[0]
        prev = first_verse.find_previous(["p", "h2", "h3", "h4", "dt", "dd"])
        if prev:
            candidate = prev.get_text(strip=True)
            if (
                candidate
                and candidate != title_line
                and 5 < len(candidate) < 50
                and "오늘의" not in candidate
                and "큐티" not in candidate
                and "관련문의" not in candidate
            ):
                subtitle = candidate
    log(f"부제: {subtitle or '(없음)'}")

    # 구절
    verses = extract_verses(soup, ref_parsed)
    log(f"구절 추출: {len(verses)}절", "OK" if verses else "WARN")

    # 질문
    questions = extract_questions(soup)
    log(f"질문 추출: {len(questions)}개")

    return {
        "date": today_str(),
        "date_label": date_label,
        "title": title,
        "subtitle": subtitle,
        "scripture_ref": scripture_ref,
        "book_name": ref_parsed["book"],
        "chapter": ref_parsed["chapter"],
        "verses_start": ref_parsed["start"],
        "verses_end": ref_parsed["end"],
        "verses_start_chapter": ref_parsed["start_chapter"],
        "verses_end_chapter": ref_parsed["end_chapter"],
        "cross_chapter": ref_parsed["cross_chapter"],
        "verses": verses,
        "oryun_questions": questions,
        # full_chapter_verses: 해당 장(chapter) 전체 구절.
        # 오륜교회 페이지는 집중 구절만 제공하므로, 별도 성경 소스에서 채워야 함.
        # TODO(Phase 2): 개역개정 전체 장 데이터 소스 연동 (공개 성경 API 또는 정적 JSON)
        "full_chapter_verses": [],
        "source_url": URL,
        "fetched_at": datetime.now(KST).isoformat(),
    }


# ===== 검증 =====
def validate(data: dict) -> tuple:
    """(critical, warnings) 반환. critical 이 비어있지 않으면 데이터를 저장하지 않는다."""
    critical = []
    warnings = []

    if not data["title"]:
        critical.append("제목이 비어있음")
    if not data["scripture_ref"]:
        critical.append("성경 구절 범위가 비어있음 (제목/구절 파싱 실패 가능)")
    if not data["verses"]:
        critical.append("구절이 하나도 없음")
    elif not data.get("cross_chapter") and data["verses_start"] and data["verses_end"]:
        # 같은 장 안의 단순 범위일 때만 절 개수를 정확히 검증
        expected = data["verses_end"] - data["verses_start"] + 1
        actual = len(data["verses"])
        if actual != expected:
            warnings.append(f"구절 개수 불일치: 예상 {expected}절, 실제 {actual}절")

    # 제목 안에 성경 구절이 그대로 섞여 들어갔는지 (파싱 실패 흔적)
    if re.search(r"\d+:\d+", data["title"]):
        critical.append(f"제목에 구절 표기가 섞여 있음: {data['title']!r}")

    return critical, warnings


# ===== 저장 =====
def save_json(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


# ===== 메인 =====
def main() -> int:
    parser = argparse.ArgumentParser(description="오륜교회 주만나 QT 크롤러")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 결과만 출력")
    parser.add_argument("--output", type=str, default=None, help="저장 경로")
    args = parser.parse_args()

    log("=" * 50)
    log("주만나 QT 크롤링 시작")
    log("=" * 50)

    try:
        html = fetch_page()
    except Exception as e:
        log(f"페이지 요청 실패: {e}", "ERR")
        log("💡 팁: VPN을 끄거나 다른 네트워크에서 시도해보세요.")
        return 1

    try:
        data = parse_qt(html)
    except Exception as e:
        log(f"파싱 실패: {e}", "ERR")
        return 2

    critical, warnings = validate(data)
    for w in warnings:
        log(w, "WARN")
    for c in critical:
        log(c, "ERR")

    log("=" * 50)
    log(f"제목:   {data['title']}")
    log(f"구절:   {data['scripture_ref']}")
    log(f"절 수:  {len(data['verses'])}")
    log(f"질문:   {len(data['oryun_questions'])}개")
    log("=" * 50)

    if critical:
        log("치명적 오류가 있어 데이터를 저장하지 않습니다 (워크플로 실패 처리).", "ERR")
        log("💡 페이지 구조나 구절 표기 형식이 바뀌었을 수 있어요 — fetch_qt.py 파싱 규칙 점검 필요.")
        return 3

    if args.dry_run:
        log("[DRY RUN] 저장하지 않고 종료합니다")
        print("\n" + json.dumps(data, ensure_ascii=False, indent=2))
    else:
        output_path = (
            Path(args.output) if args.output
            else DEFAULT_OUTPUT_DIR / f"{data['date']}.json"
        )
        save_json(data, output_path)
        log(f"저장 완료: {output_path}", "OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
