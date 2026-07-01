# -*- coding: utf-8 -*-
"""
자동 KB(지식 밑반찬) 생성기 — 파이프라인 ② 단계.

그날 본문(data/qt/{date}.json)의 책·장을 보고, data/reference/{책}.json 에
해당 장 지식이 없으면 AI로 조사해 채웁니다. 이미 있으면 건너뜁니다(재사용).

★ 안전 원칙
  - 이미 있는 장은 절대 덮어쓰지 않습니다(손수 만든 검증 KB 보존).
  - 생성물은 top-level에 _auto:true / _generated 로 "AI생성·미검증" 표시 →
    2주차에 진짜 신학 자료와 대조·검증하기 쉽게.
  - 출력 형식은 5단 호흡(generate_meditation.py)이 읽는 스키마와 100% 동일.
    (각 장: key_details / 인물 / 신학_핵심 / 주의점)

사용법
  python scripts/generate_kb.py                 # 오늘 본문 기준
  python scripts/generate_kb.py 2026-07-01      # 특정 날짜
  python scripts/generate_kb.py --force         # 이미 있어도 재생성
  python scripts/generate_kb.py --dry-run       # 생성 없이 계획만 출력(무료)

종료 코드: 0 = 성공/정상 skip · 1 = 입력 오류 · 2 = 생성 실패
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ===== 설정 =====
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
QT_DIR = PROJECT_ROOT / "data" / "qt"
REF_DIR = PROJECT_ROOT / "data" / "reference"

MODEL = "gpt-4o"          # 기존 파이프라인과 동일 모델
TEMPERATURE = 0.3         # 사실 조사이므로 낮게 — 덜 지어내게
MAX_TOKENS = 3000

PRICE_INPUT_PER_1M = 2.50
PRICE_OUTPUT_PER_1M = 10.00
USD_TO_KRW = 1500


# ===== 로깅 =====
def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now(KST).strftime("%H:%M:%S")
    prefix = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "SKIP": "⏭️ "}.get(level, "• ")
    print(f"[{now}] {prefix} {msg}")


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


# ===== 입력 로드 =====
def load_qt_data(date_str: str) -> dict:
    qt_path = QT_DIR / f"{date_str}.json"
    if not qt_path.exists():
        raise FileNotFoundError(
            f"{qt_path}를 찾을 수 없습니다. 먼저 fetch_qt.py로 QT 데이터를 준비하세요."
        )
    return json.loads(qt_path.read_text(encoding="utf-8"))


def chapters_of(qt_data: dict) -> list[str]:
    """그날 본문이 걸친 장 번호(문자열) 목록. slice_kb_to_passage와 동일 규칙."""
    cstart = qt_data.get("verses_start_chapter") or qt_data.get("chapter")
    cend = qt_data.get("verses_end_chapter") or qt_data.get("chapter") or cstart
    if not cstart:
        return []
    return [str(c) for c in range(int(cstart), int(cend) + 1)]


# ===== 프롬프트 =====
SYSTEM_PROMPT = """당신은 개혁주의·복음주의 전통에 충실한 성경 주석 조사원입니다.
주어진 성경 '한 장'에 대해, 큐티 묵상 집필에 쓸 **검증 가능한 사실 지식(KB)**을 JSON으로 정리합니다.

[수집·서술 원칙 — 반드시 지킬 것]
1. 본문 관찰이 먼저입니다. 본문이 실제로 말하는 것에서 출발하세요.
2. **추측 금지.** 확실하지 않으면 넣지 말거나 confidence를 낮추고, 불확실함을 명시하세요.
   특히 히브리어 어원·지명 위치·숫자는 표준적으로 확실한 것만 적습니다. 어원을 지어내지 마세요.
3. 정통 안에서도 견해가 갈리는 지점(인물/사물의 정체, 번역 차이, 사건 해석)은
   반드시 '주의점'에 "견해가 갈린다"고 명시하고, 한쪽으로 단정하지 마세요.
4. source에는 근거를 적되(예: "ESV Study", "Keil&Delitzsch", "Strong's H####", "개역개정 본문 관찰"),
   확실치 않으면 "일반 지식(미확정)"이라고 정직하게 적으세요. 없는 출처를 지어내지 마세요.
5. 과도한 도덕적 정죄나 인물 미화를 피하고, 본문이 말하는 범위를 넘지 마세요.

[출력 형식 — 오직 JSON 객체 하나. 설명 문장 금지]
{
  "key_details": [
    {"verse": "장:절 또는 장:절-절", "cat": "지리|어원|신학핵심|본문관찰|인물배경",
     "fact": "한 문장으로 명료하게", "source": "근거", "confidence": "high|medium|low"}
  ],
  "인물": [
    {"인물": "이름", "상황": "이 장에서의 처지·행동", "감정": "내면·긴장"}
  ],
  "신학_핵심": "이 장이 드러내는 하나님은 어떤 분인가 — 2~3문장",
  "주의점": ["묵상 시 오해·과장을 막을 경고들(견해차 포함)"]
}

key_details는 6~9개, 인물은 1~3명. 한국어로 작성하세요."""


def build_user_prompt(qt_data: dict, chapter: str) -> str:
    book = qt_data.get("book_name", "")
    ref = qt_data.get("scripture_ref", "")
    verses = qt_data.get("verses", [])
    body = "\n".join(f"{v.get('number','')} {v.get('text','')}" for v in verses)
    return json.dumps({
        "책": book,
        "장": chapter,
        "오늘_본문_참조": ref,
        "오늘_본문_절": body,
        "지시": (
            f"위는 '{book} {chapter}장'에 속한 오늘 큐티 본문입니다. "
            f"'{book} {chapter}장' 전체를 대상으로, 이 본문 묵상에 도움이 될 KB를 위 형식으로 정리하세요. "
            "제공된 절 밖의 내용도 그 장에 속하면 당신의 지식으로 보완하되, 원칙(추측 금지·견해차 명시)을 지키세요."
        ),
    }, ensure_ascii=False)


# ===== 비용 =====
def calc_cost(usage) -> dict:
    cost_usd = (
        usage.prompt_tokens / 1_000_000 * PRICE_INPUT_PER_1M
        + usage.completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M
    )
    return {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_krw": round(cost_usd * USD_TO_KRW, 2),
    }


# ===== 생성 =====
def get_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 라이브러리가 없습니다. pip install openai python-dotenv")
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        log("python-dotenv가 없습니다. 환경변수 직접 사용.", "WARN")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다. .env 또는 환경변수로 설정하세요.")
    return OpenAI(api_key=api_key)


def generate_chapter_kb(client, qt_data: dict, chapter: str) -> tuple[dict, dict]:
    """한 장의 KB를 생성해 (chapter_dict, cost) 반환."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(qt_data, chapter)},
        ],
        response_format={"type": "json_object"},
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    data = json.loads(response.choices[0].message.content)
    cost = calc_cost(response.usage)

    # 스키마 최소 검증 — 어긋나면 예외로 올려 파이프라인이 KB 없이 진행하게 함
    if not isinstance(data.get("key_details"), list) or not data["key_details"]:
        raise ValueError("key_details가 비어 있거나 리스트가 아님")
    if not isinstance(data.get("인물"), list):
        raise ValueError("인물이 리스트가 아님")
    if not data.get("신학_핵심"):
        raise ValueError("신학_핵심이 비어 있음")
    data.setdefault("주의점", [])

    # 필요한 키만 정갈하게 남김 (5단 호흡이 읽는 형식과 동일)
    chapter_dict = {
        "key_details": data["key_details"],
        "인물": data["인물"],
        "신학_핵심": data["신학_핵심"],
        "주의점": data["주의점"],
    }
    return chapter_dict, cost


# ===== 저장 =====
def save_kb(book: str, kb: dict) -> Path:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    path = REF_DIR / f"{book}.json"
    path.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ===== 메인 =====
def main() -> int:
    parser = argparse.ArgumentParser(description="자동 KB 생성기 (파이프라인 ② 단계)")
    parser.add_argument("date_pos", nargs="?", default=None, help="날짜 YYYY-MM-DD (생략 시 오늘)")
    parser.add_argument("--date", default=None, help="날짜 (positional 대신)")
    parser.add_argument("--force", action="store_true", help="이미 있어도 재생성")
    parser.add_argument("--dry-run", action="store_true", help="생성 없이 계획만 출력(무료)")
    args = parser.parse_args()

    date = args.date or args.date_pos or today_str()

    log("=" * 50)
    log(f"자동 KB 생성 시작 (날짜: {date})")

    # 1) 입력 로드
    try:
        qt_data = load_qt_data(date)
    except FileNotFoundError as e:
        log(str(e), "ERR")
        return 1

    book = qt_data.get("book_name", "")
    if not book:
        log("qt 데이터에 book_name이 없습니다 → KB 생성 건너뜀", "WARN")
        return 0

    chapters = chapters_of(qt_data)
    if not chapters:
        log("본문 장 번호를 알 수 없습니다 → KB 생성 건너뜀", "WARN")
        return 0

    log(f"본문: {qt_data.get('scripture_ref','')} · 책='{book}' · 장={chapters}")

    # 2) 기존 KB 로드 (있으면 보존, 없으면 새로)
    ref_path = REF_DIR / f"{book}.json"
    if ref_path.exists():
        try:
            kb = json.loads(ref_path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"기존 KB 읽기 실패({e}) → 새로 만들지 않고 중단(덮어쓰기 방지)", "ERR")
            return 2
    else:
        kb = {"book": book}

    # 3) 채울 장 결정 (이미 있으면 건너뜀 = 재실행 방어)
    missing = [c for c in chapters if c not in kb or args.force]
    already = [c for c in chapters if c in kb and not args.force]
    if already:
        log(f"이미 있는 장(건너뜀): {already}", "SKIP")
    if not missing:
        log("생성할 장이 없습니다 → 정상 종료(재사용)", "OK")
        return 0

    log(f"생성할 장: {missing}")

    if args.dry_run:
        log("[DRY RUN] 실제 생성 없이 종료합니다.")
        return 0

    # 4) 생성
    try:
        client = get_client()
    except RuntimeError as e:
        log(str(e), "ERR")
        return 2

    kb.setdefault("_auto", True)
    kb.setdefault("_note", "AI 자동 생성 KB(미검증). 2주차에 신학 자료 대조·검증 예정. "
                           "confidence·source를 참고하고, 어원·정체·번역 견해차는 주의점 확인.")
    generated = kb.setdefault("_generated", {})

    total_krw = 0.0
    made = []
    for ch in missing:
        try:
            log(f"[{book} {ch}장] 조사 중 (model={MODEL})...")
            chapter_dict, cost = generate_chapter_kb(client, qt_data, ch)
            kb[ch] = chapter_dict
            generated[ch] = {"at": datetime.now(KST).isoformat(), "model": MODEL}
            total_krw += cost["cost_krw"]
            made.append(ch)
            log(f"[{book} {ch}장] 완료 — key_details {len(chapter_dict['key_details'])}개 "
                f"/ 인물 {len(chapter_dict['인물'])}명 / 약 {cost['cost_krw']:.1f}원", "OK")
        except Exception as e:
            log(f"[{book} {ch}장] 생성 실패: {e}", "ERR")

    if not made:
        log("생성된 장이 없습니다 → 저장 안 함", "ERR")
        return 2

    # 5) 저장 (성공한 장만 반영된 상태로)
    path = save_kb(book, kb)
    log("=" * 50)
    log(f"저장 완료: {path} · 새 장 {made} · 합계 약 {total_krw:.1f}원", "OK")
    log("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
