"""
주만나 AI 묵상 생성기
====================================
오륜교회 주만나 QT JSON을 입력받아 AI 묵상 콘텐츠를 생성합니다.

사용법:
    # Mock 모드 (API 호출 없이 샘플 생성)
    python scripts/generate_ai.py --mock

    # 실제 모드 (.env 에 OPENAI_API_KEY 필요)
    python scripts/generate_ai.py

    # 특정 날짜 지정
    python scripts/generate_ai.py --date 2026-04-22

    # 드라이런 (저장하지 않고 결과만 출력)
    python scripts/generate_ai.py --dry-run

필요 환경:
    pip install openai python-dotenv
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ===== 설정 =====
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
QT_DIR = PROJECT_ROOT / "data" / "qt"
AI_DIR = PROJECT_ROOT / "data" / "ai"

MODEL = "gpt-4o-mini"
# 가격 (2026년 기준, 백만 토큰당)
PRICE_INPUT_PER_1M = 0.15  # USD
PRICE_OUTPUT_PER_1M = 0.60  # USD
USD_TO_KRW = 1350  # 대략적인 환율

# 금지어 (AI_PROMPT.md 기준)
FORBIDDEN_WORDS = ["여러분", "~해야만", "반드시 해야"]


# ===== 로깅 =====
def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now(KST).strftime("%H:%M:%S")
    prefix = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "MOCK": "🎭"}.get(level, "• ")
    print(f"[{now}] {prefix} {msg}")


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


# ===== 프롬프트 =====
SYSTEM_PROMPT = """당신은 따뜻한 목사님이면서 동시에 지혜로운 멘토입니다.
성경을 깊이 사랑하며, 사람들의 일상에 말씀을 연결해주는 데에 탁월합니다.

[말투 원칙]
- 존댓말 사용 (~합니다, ~입니다)
- 딱딱하지 않고 따뜻하게
- 한 문장을 짧게 끊어서 쓰기 (초원 앱 스타일)
- 신학 용어는 최소화, 썼을 때는 반드시 풀어서 설명
- 훈계하지 않고 함께 생각하는 톤

[절대 하지 말아야 할 것]
- "~라고 생각해보세요" 같은 강요
- 정치적/논쟁적 해석
- 특정 교단의 편향된 해석
- "여러분은 어떻게 생각하시나요?" 같은 반문
- 너무 긴 문장

[반드시 포함해야 할 것]
- 말씀을 오늘 독자의 일상과 연결
- 등장인물의 감정에 공감
- 희망적이고 은혜로운 결론"""


def build_user_prompt(qt_data: dict) -> str:
    """QT 원본 데이터로부터 사용자 프롬프트 생성"""
    verses_text = "\n".join(
        f"{v['number']} {v['text']}" for v in qt_data["verses"]
    )

    return f"""아래 성경 본문을 바탕으로 오늘의 묵상 콘텐츠를 JSON으로 생성해주세요.

[성경 본문]
제목: {qt_data['title']}
구절: {qt_data['scripture_ref']}
부제: {qt_data.get('subtitle', '')}
본문:
{verses_text}

[요구사항]
1. core_summary: 본문의 핵심을 정확히 5개의 짧은 문장으로 요약. 각 문장은 한 줄로 끝나게.
2. characters: 본문에 등장하는 주요 인물 1~3명. 각 인물당 2~3문장 설명.
3. book_context: 이 책({qt_data['book_name']})의 전체 흐름과 이 구절의 위치. 3~4문장.
4. verse_commentary: 본문에서 주목할 만한 단어, 배경, 의미. 3~5문장.
5. application: 내 삶에 적용할 문장 3개. 각각 "나는 오늘, ~하겠습니다. [보조설명]" 형식.
6. prayer: 기도문. 8~14줄. 초원 앱처럼 짧게 줄바꿈된 시적인 형태 (빈 줄 포함 가능).

[스타일]
- 모든 텍스트는 한국어
- 짧은 문장, 많은 줄바꿈 (모바일 가독성)
- 따뜻하고 부드러운 톤
- 의역하지 말고 본문에 충실하게

JSON 형식으로만 응답하고, 다음 구조를 따르세요:
{{
  "core_summary": ["문장1", "문장2", "문장3", "문장4", "문장5"],
  "characters": [
    {{"name": "이름", "description": "설명"}}
  ],
  "book_context": "책 전체 맥락 설명",
  "verse_commentary": "구절 해설",
  "application": [
    {{"statement": "나는 오늘, ~하겠습니다.", "detail": "보조 설명"}}
  ],
  "prayer": ["주님,", "", "첫 번째 문장.", "두 번째 문장.", "", "..."]
}}"""


# ===== Mock 모드 =====
def generate_mock(qt_data: dict) -> dict:
    """Mock 응답 생성 (오늘 4/22 룻기 기준)"""
    log("Mock 모드로 샘플 응답을 생성합니다", "MOCK")

    # 실제 본문 기반 sample (룻기 1:15-22)
    # 다른 날짜에도 동작하도록 일반화된 샘플도 준비
    if qt_data.get("book_name") == "룻기" and qt_data.get("chapter") == 1:
        return _mock_ruth_1(qt_data)

    # 그 외의 경우 - 제네릭 샘플
    return _mock_generic(qt_data)


def _mock_ruth_1(qt_data: dict) -> dict:
    """룻기 1장 맞춤 샘플 (4/22 실제 본문용)"""
    return {
        "core_summary": [
            "룻은 나오미를 떠나지 않고 함께 가기로 결심합니다.",
            "\"어머니의 하나님이 나의 하나님이 되시리니\"",
            "나오미는 자신을 '마라'로 불러달라 합니다.",
            "두 여인은 베들레헴에 도착합니다.",
            "상실의 끝에서 회복이 시작됩니다."
        ],
        "characters": [
            {
                "name": "나오미",
                "description": "'즐거움'이란 이름을 가진 이스라엘 여인입니다. 남편과 두 아들을 모압 땅에서 잃고 빈손으로 고향에 돌아옵니다. 이제 자신을 '마라(쓰라림)'라고 불러달라 할 만큼 삶이 고통스럽습니다."
            },
            {
                "name": "룻",
                "description": "모압 여인이자 나오미의 며느리입니다. 남편을 잃고도 시어머니를 떠나지 않기로 결심합니다. 이방인의 길을 감수하며 헌신을 택한 사람입니다."
            }
        ],
        "book_context": "룻기는 사사시대라는 혼란의 시기에 피어난 한 이방 여인의 헌신과 회복의 이야기입니다. 짧지만 강렬한 이 책은 '상실'에서 '회복'으로 이어지는 하나님의 섬세한 인도를 보여줍니다. 훗날 룻은 다윗의 증조모가 되어 예수 그리스도의 족보에 오르게 됩니다. 오늘 본문은 이 거대한 이야기의 시작점입니다.",
        "verse_commentary": "'마라'는 히브리어로 '쓴맛'을 뜻합니다. 나오미는 자신의 고통을 숨기지 않고 솔직히 토로합니다. 그런데 본문 마지막에 '보리 추수가 시작될 때'라는 표현이 덧붙여집니다. 이는 단순한 시간 정보가 아닙니다. 비어 돌아온 그녀에게 다시 채우심이 시작될 것을 알리는 복선입니다.",
        "application": [
            {
                "statement": "나는 오늘, 상실 앞에서 솔직해지겠습니다.",
                "detail": "감정을 숨기지 않고 하나님께 내어놓겠습니다."
            },
            {
                "statement": "나는 오늘, 떠나지 않는 사람이 되겠습니다.",
                "detail": "어려움 속에서도 관계를 붙들겠습니다."
            },
            {
                "statement": "나는 오늘, 보리 추수를 기대하겠습니다.",
                "detail": "비어 있는 자리에 채우실 하나님을 신뢰하겠습니다."
            }
        ],
        "prayer": [
            "주님,",
            "비어 돌아온 나오미에게",
            "보리 추수의 때를 허락하신 주님.",
            "",
            "저의 쓰라린 자리에도",
            "회복의 계절을 보내주옵소서.",
            "",
            "룻처럼 흔들리지 않는 헌신으로",
            "주님을 따르게 하시고,",
            "",
            "나오미처럼 솔직하게",
            "주님께 아뢰게 하옵소서.",
            "",
            "예수님의 이름으로 기도합니다. 아멘."
        ]
    }


def _mock_generic(qt_data: dict) -> dict:
    """임의 날짜에도 동작하는 제네릭 샘플"""
    title = qt_data.get("title", "오늘의 말씀")
    book = qt_data.get("book_name", "성경")

    return {
        "core_summary": [
            f"오늘 본문은 '{title}'이라는 주제를 담고 있습니다.",
            "하나님은 말씀을 통해 우리에게 다가오십니다.",
            "본문 속 인물들의 삶에 주목합니다.",
            "그들의 선택은 우리에게 교훈을 남깁니다.",
            "오늘 이 말씀이 나의 이야기가 되길 소망합니다."
        ],
        "characters": [
            {
                "name": "주요 인물",
                "description": f"{book} 본문에 등장하는 주요 인물입니다. 삶의 순간마다 하나님의 임재를 경험합니다. 이들의 이야기는 오늘 우리에게도 살아있는 말씀입니다."
            }
        ],
        "book_context": f"{book}은 구약/신약 성경의 한 부분으로, 하나님의 구원 역사를 보여주는 중요한 책입니다. 오늘 본문은 이 책의 큰 흐름 속에서 특별한 위치를 차지합니다. 전체 맥락을 이해하면 본문의 의미가 더 풍성해집니다.",
        "verse_commentary": "오늘 본문에서 주목할 만한 표현들이 있습니다. 성경 원어의 뉘앙스와 당시 역사적 배경을 함께 살펴보면 본문이 더 깊이 이해됩니다. 하나님은 말씀을 통해 오늘도 우리에게 말씀하십니다.",
        "application": [
            {
                "statement": "나는 오늘, 말씀에 귀 기울이겠습니다.",
                "detail": "바쁜 일상 속에서도 잠시 멈춰 주님의 음성을 듣겠습니다."
            },
            {
                "statement": "나는 오늘, 믿음으로 한 걸음 나아가겠습니다.",
                "detail": "두려움이 아닌 믿음으로 선택하겠습니다."
            },
            {
                "statement": "나는 오늘, 감사하는 마음을 잃지 않겠습니다.",
                "detail": "작은 것에도 감사함을 발견하겠습니다."
            }
        ],
        "prayer": [
            "주님,",
            "오늘도 말씀으로 저를 만나주심에",
            "감사합니다.",
            "",
            "이 말씀이 제 삶에",
            "살아 움직이게 하옵소서.",
            "",
            "주님의 뜻을 따라",
            "오늘을 살아가게 하소서.",
            "",
            "예수님의 이름으로 기도합니다.",
            "아멘."
        ]
    }


# ===== 실제 API 호출 =====
def generate_real(qt_data: dict) -> tuple:
    """OpenAI API로 실제 생성. (ai_data, cost_info) 튜플 반환"""
    try:
        from openai import OpenAI
    except ImportError:
        log("openai 라이브러리가 설치되지 않았습니다.", "ERR")
        log("설치: pip install openai python-dotenv")
        raise

    # .env 로드
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        log("python-dotenv가 없습니다. 환경변수 직접 사용.", "WARN")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 없습니다. .env 파일에 추가하거나 환경변수로 설정하세요."
        )

    client = OpenAI(api_key=api_key)
    user_prompt = build_user_prompt(qt_data)

    log(f"OpenAI API 호출 중 (모델: {MODEL})...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    content = response.choices[0].message.content
    ai_data = json.loads(content)

    # 비용 계산
    usage = response.usage
    cost_usd = (
        usage.prompt_tokens / 1_000_000 * PRICE_INPUT_PER_1M
        + usage.completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M
    )
    cost_info = {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_krw": round(cost_usd * USD_TO_KRW, 2),
    }

    log(
        f"토큰: {usage.prompt_tokens}(입력) + {usage.completion_tokens}(출력) "
        f"= {usage.total_tokens}",
        "OK"
    )
    log(
        f"비용: ${cost_info['cost_usd']:.6f} (약 {cost_info['cost_krw']:.2f}원)",
        "OK"
    )

    return ai_data, cost_info


# ===== 검증 =====
def validate(ai_data: dict) -> list:
    """AI_PROMPT.md 기준으로 검증. 경고 리스트 반환."""
    warnings = []

    # core_summary: 5줄
    summary = ai_data.get("core_summary", [])
    if len(summary) != 5:
        warnings.append(f"core_summary가 정확히 5줄이 아님 (현재 {len(summary)}줄)")

    # characters: 1~3명
    chars = ai_data.get("characters", [])
    if not (1 <= len(chars) <= 3):
        warnings.append(f"characters가 1~3명 범위를 벗어남 (현재 {len(chars)}명)")

    # application: 정확히 3개
    app = ai_data.get("application", [])
    if len(app) != 3:
        warnings.append(f"application이 정확히 3개가 아님 (현재 {len(app)}개)")

    # prayer: 8~14줄
    prayer = ai_data.get("prayer", [])
    if not (8 <= len(prayer) <= 14):
        warnings.append(f"prayer가 8~14줄 범위를 벗어남 (현재 {len(prayer)}줄)")

    # 금지어 검사
    all_text = json.dumps(ai_data, ensure_ascii=False)
    for word in FORBIDDEN_WORDS:
        if word in all_text:
            warnings.append(f"금지어 포함: '{word}'")

    return warnings


# ===== 저장 =====
def save_json(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


# ===== 입력 QT 로드 =====
def load_qt_data(date_str: str) -> dict:
    qt_path = QT_DIR / f"{date_str}.json"
    if not qt_path.exists():
        raise FileNotFoundError(
            f"{qt_path}를 찾을 수 없습니다. "
            f"먼저 fetch_qt.py를 실행해 QT 데이터를 준비하세요."
        )
    return json.loads(qt_path.read_text(encoding="utf-8"))


# ===== 메인 =====
def main() -> int:
    parser = argparse.ArgumentParser(description="주만나 AI 묵상 생성기")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="API 호출 없이 Mock 응답 사용",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="처리할 날짜 (YYYY-MM-DD). 기본값: 오늘",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="저장하지 않고 결과만 출력",
    )
    args = parser.parse_args()

    date = args.date or today_str()

    log("=" * 50)
    log(f"AI 묵상 생성 시작 (날짜: {date}, 모드: {'Mock' if args.mock else 'Real'})")
    log("=" * 50)

    # 1. QT 데이터 로드
    try:
        qt_data = load_qt_data(date)
        log(f"QT 데이터 로드: {qt_data['title']} ({qt_data['scripture_ref']})", "OK")
    except FileNotFoundError as e:
        log(str(e), "ERR")
        return 1

    # 2. AI 생성
    cost_info = None
    try:
        if args.mock:
            ai_data = generate_mock(qt_data)
        else:
            ai_data, cost_info = generate_real(qt_data)
    except Exception as e:
        log(f"AI 생성 실패: {e}", "ERR")
        return 2

    # 3. 검증
    warnings = validate(ai_data)
    if warnings:
        for w in warnings:
            log(w, "WARN")
    else:
        log("검증 통과 ✓", "OK")

    # 4. 메타데이터 추가
    result = {
        "date": date,
        "scripture_ref": qt_data["scripture_ref"],
        "title": qt_data["title"],
        **ai_data,
        "generated_at": datetime.now(KST).isoformat(),
        "model": "mock" if args.mock else MODEL,
    }
    if cost_info:
        result["_cost"] = cost_info

    # 5. 저장
    if args.dry_run:
        log("[DRY RUN] 저장하지 않고 종료합니다")
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))
    else:
        output_path = AI_DIR / f"{date}.json"
        save_json(result, output_path)
        log(f"저장 완료: {output_path}", "OK")

    log("=" * 50)
    log(f"요약:     {len(ai_data.get('core_summary', []))}줄")
    log(f"인물:     {len(ai_data.get('characters', []))}명")
    log(f"적용:     {len(ai_data.get('application', []))}개")
    log(f"기도문:   {len(ai_data.get('prayer', []))}줄")
    log("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
