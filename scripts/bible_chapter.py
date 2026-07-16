# -*- coding: utf-8 -*-
"""
장(章) 전체 본문 조회 — generate_kb.py 보조 모듈.

배경: 오륜교회 주만나 페이지는 '그날 집중 구절'만 제공한다(fetch_qt.py의
full_chapter_verses가 늘 빈 배열인 이유). 그래서 KB 생성기가 모델에게
그날 절만 넘기고 "나머지 장은 네 지식으로 보완하라"고 말로만 부탁해 왔고,
모델은 실제로 보완하지 않았다.

  실측(2026-07-15): 사무엘하 6장 KB의 key_details 8개가 전부 6:1-11에만 붙어 있음.
  6장 KB는 7/13(본문 6:1-11)에 만들어졌고, KB는 장 단위로 skip되므로
  7/14(본문 6:12-23)는 지식 0개로 묵상이 생성됐다.

이 모듈은 대한성서공회에서 개역개정 '장 전체'를 가져와 그 구멍을 막는다.
순수 HTTP 요청이라 비용 0원. 실패하면 조용히 None을 돌려주고, 호출부는
기존 방식(그날 절만)으로 폴백한다 — KB 생성 자체가 막히면 안 되므로.
"""
import re
import time

from bs4 import BeautifulSoup

try:
    import requests
except ImportError:  # 파이프라인이 이 모듈 때문에 죽지 않게
    requests = None

USER_AGENT = "Mozilla/5.0 (compatible; personal-qt-kb-research/1.0; non-commercial verse study tool)"
REQUEST_TIMEOUT = 12
RETRIES = 3
RETRY_DELAY = 2.0

BASE = "https://www.bskorea.or.kr/bible/korbibReadpage.php"
VERSION = "GAE"  # 개역개정

# 대한성서공회 book 슬러그. 2026-07-15에 창세기·출애굽기·사무엘상하·열왕기상·역대상·
# 시편·잠언·이사야·마태·요한·사도행전·로마서·요한계시록·사사기·룻기를 실제 조회해
# 1장 절 수가 실제와 일치함을 확인함.
BOOK_SLUGS = {
    "창세기": "gen", "출애굽기": "exo", "레위기": "lev", "민수기": "num", "신명기": "deu",
    "여호수아": "jos", "사사기": "jdg", "룻기": "rut",
    "사무엘상": "1sa", "사무엘하": "2sa", "열왕기상": "1ki", "열왕기하": "2ki",
    "역대상": "1ch", "역대하": "2ch", "에스라": "ezr", "느헤미야": "neh", "에스더": "est",
    "욥기": "job", "시편": "psa", "잠언": "pro", "전도서": "ecc", "아가": "sng",
    "이사야": "isa", "예레미야": "jer", "예레미야애가": "lam", "에스겔": "ezk", "다니엘": "dan",
    "호세아": "hos", "요엘": "jol", "아모스": "amo", "오바댜": "oba", "요나": "jon",
    "미가": "mic", "나훔": "nam", "하박국": "hab", "스바냐": "zep", "학개": "hag",
    "스가랴": "zec", "말라기": "mal",
    "마태복음": "mat", "마가복음": "mrk", "누가복음": "luk", "요한복음": "jhn",
    "사도행전": "act", "로마서": "rom", "고린도전서": "1co", "고린도후서": "2co",
    "갈라디아서": "gal", "에베소서": "eph", "빌립보서": "php", "골로새서": "col",
    "데살로니가전서": "1th", "데살로니가후서": "2th", "디모데전서": "1ti", "디모데후서": "2ti",
    "디도서": "tit", "빌레몬서": "phm", "히브리서": "heb", "야고보서": "jas",
    "베드로전서": "1pe", "베드로후서": "2pe", "요한일서": "1jn", "요한이서": "2jn",
    "요한삼서": "3jn", "유다서": "jud", "요한계시록": "rev",
}


def _get(url: str) -> str | None:
    if requests is None:
        return None
    for attempt in range(RETRIES):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        if attempt < RETRIES - 1:
            time.sleep(RETRY_DELAY)
    return None


def fetch_chapter(book: str, chapter: int, log=None) -> list[dict] | None:
    """개역개정 한 장 전체를 [{"number": 1, "text": "..."}, ...]로. 실패하면 None."""
    slug = BOOK_SLUGS.get(book)
    if not slug:
        if log:
            log(f"  장 전체 조회: 책 매핑 없음('{book}') → 그날 본문만으로 진행", "WARN")
        return None

    html = _get(f"{BASE}?version={VERSION}&book={slug}&chap={int(chapter)}&sec=1")
    if not html:
        if log:
            log(f"  장 전체 조회 실패({book} {chapter}장) → 그날 본문만으로 진행", "WARN")
        return None

    root = BeautifulSoup(html, "lxml").select_one("#tdBible1")
    if root is None:
        if log:
            log("  장 전체 조회: 페이지 구조가 바뀐 듯함 → 그날 본문만으로 진행", "WARN")
        return None

    verses = []
    for marker in root.select("span.number"):
        num = marker.get_text(strip=True)
        if not num.isdigit():
            continue
        # 절 번호 span 다음부터 그 다음 절 번호 span 직전까지가 본문
        # (고유명사가 <a class="name">으로 감싸여 있어 get_text로 이어 붙여야 한다)
        chunks = []
        for sib in marker.next_siblings:
            classes = sib.get("class") or [] if hasattr(sib, "get") else []
            if "number" in classes:
                break
            chunks.append(sib.get_text("") if hasattr(sib, "get_text") else str(sib))
        text = re.sub(r"\s+", " ", "".join(chunks)).strip()
        if text:
            verses.append({"number": int(num), "text": text})

    if not verses:
        return None
    verses.sort(key=lambda v: v["number"])
    if log:
        log(f"  장 전체 조회 완료: {book} {chapter}장 {len(verses)}절", "OK")
    return verses


if __name__ == "__main__":  # 수동 점검용
    import sys
    b = sys.argv[1] if len(sys.argv) > 1 else "사무엘하"
    c = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    vs = fetch_chapter(b, c)
    print(f"{b} {c}장 — {len(vs) if vs else 0}절")
    for v in (vs or [])[:3]:
        print(f"  {v['number']} {v['text']}")
