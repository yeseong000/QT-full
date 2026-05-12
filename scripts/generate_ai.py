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
USD_TO_KRW = 1500  # 대략적인 환율

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
- 한 문장을 짧게 끊어서 쓰기 
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
1. scenes: 본문의 핵심 장면을 정확히 5개의 짧은 문장으로 묘사. 각 문장은 한 줄로 끝나게.
2. characters: 본문에 등장하는 주요 인물 1~3명. 각 인물당 2~3문장 설명.
3. book_overview: 이 책({qt_data['book_name']}) 전체에 대한 소개. 오늘 본문이나 특정 구절은 절대 언급하지 말 것.
   다음 4개 필드를 가진 **객체(JSON object)** 로 출력:

   - "author" (저자): 누가 썼다고 전해지는지. 가능하면 한두 어절로 짧게 (예: "사도바울",
     "전통적으로 사무엘로 전해짐"). 저자 논쟁이 있는 책(히브리서, 베드로후서, 모세오경,
     이사야, 욥기 등)은 "알려져 있지 않음", "여러 견해가 있음" 같은 완충 표현 필수. 단정 금지.

   - "date" (시기): 대략의 기록 시기를 한 줄로 짧게
     (예: "AD 60~63년경 추정", "사사 시대 후 후대에 정리"). 정확한 연도 단정 금지.

   - "place" (기록 장소와 대상): 어디서 누구를 위해 쓰였는지 자연스러운 한 문장
     (예: "로마의 감옥에서 썼으며 에베소에 있는 그리스도인을 위해 씀.").
     알 수 없으면 "정확한 기록 장소는 알려져 있지 않습니다" 식으로 처리.

   - "core" (핵심 내용): 책 전체 줄거리·핵심 메시지. 1~2문장. 특정 구절 인용 금지.

   톤: 한국어, 존댓말, 따뜻한 ~이에요/~습니다 체. 신학용어는 풀어 설명.
   교단 편향·논쟁적 해석 금지.
4. passage_intro: 오늘 본문이 이 책의 흐름 안에서 어디에 위치하는지. 정확히 1문장.
5. verse_commentary: 본문에서 주목할 만한 단어, 배경, 의미. 3~5문장.
6. application: "말씀 적용하기" 3개.

   [작성 원칙]
   - 본문에 직접 연결, 본문에 없는 내용 금지
   - 보편 문구 금지 (예: "작은 것에도 감사", "말씀에 귀 기울이기" 같이 아무 본문에나 적용되는 문구)
   - 위계적·시혜적 표현 금지 (독자를 '베푸는 자'로 세우는 표현)
     ❌ "주변 사람에게 은혜를 베풀겠습니다", "이웃을 가르치겠습니다"
     ✅ "사랑을 실천하겠습니다", "감사를 표현하겠습니다" 같은 자연스러운 결단은 허용

   [자기 낮춤 — 저/제만 사용]
   ✅ "저는 / 제 / 저의 / 저에게"
   ❌ "나는 / 내 / 나의 / 나에게"

   [시작 구조 — 다양성을 위해 매우 중요]
   세 항목은 반드시 서로 다른 단어로 시작해야 합니다.
   같은 말씀을 여러 각도에서 적용하는 다양성을 확보하기 위함입니다.
   - 1번: "저는 오늘, ~"   (반드시 이 형태)
   - 2번: "오늘부터, ~" / "이 말씀 앞에서, ~" / "주님, 제가 ~" 중 하나
   - 3번: 1번·2번과 겹치지 않는 또 다른 시작
     예: "지금 제가 ~", "이 본문이 보여주는 ~", "말씀을 따라 ~",
         "하루를 열며, ~", "주님의 마음으로, ~"
   ※ 세 항목이 모두 "저는 오늘,"로 시작하면 규칙 위반입니다.

   [문장 규칙]
   - 각 항목 정확히 2문장
   - statement = 첫 문장: 결단형 적용 (짧고 단정)
   - detail = 두 번째 문장: 본문과 연결된 보완 문장 (짧고 단정)

7. prayer: 기도문. 11줄 내외(빈 줄 포함 10~13줄 목표). 초원 앱처럼 짧게 줄바꿈된 시적인 형태.
   - 오늘 본문 등장인물의 감정이나 상황을 먼저 공감하며 시작
   - 그 인물의 이야기에서 '나'의 이야기로 자연스럽게 전환
   - 본문의 핵심 단어나 장면을 기도 안에 한 번 이상 녹여 넣기
   - 마지막은 예수님 이름으로 마무리

[스타일]
- 모든 텍스트는 한국어
- 짧은 문장, 많은 줄바꿈 (모바일 가독성)
- 따뜻하고 부드러운 톤
- 의역하지 말고 본문에 충실하게

JSON 형식으로만 응답하고, 다음 구조를 따르세요:
{{
  "scenes": ["문장1", "문장2", "문장3", "문장4", "문장5"],
  "characters": [
    {{"name": "이름", "description": "설명"}}
  ],
  "book_overview": {{
    "author": "저자 (한두 어절 또는 회피 어구)",
    "date": "대략적 시기 한 줄",
    "place": "어디서 누구를 위해 쓰였는지 (한 문장)",
    "core": "책 전체 줄거리·메시지 (1~2문장, 특정 구절 인용 금지)"
  }},
  "passage_intro": "오늘 본문의 위치 (정확히 1문장)",
  "verse_commentary": "구절 해설",
  "application": [
    {{"statement": "저는 오늘, ~.", "detail": "본문과 연결된 짧은 보완 문장 (저/제 사용)."}},
    {{"statement": "(변주형 시작) ~.", "detail": "본문과 연결된 짧은 보완 문장 (저/제 사용)."}},
    {{"statement": "(또 다른 변주형 시작) ~.", "detail": "본문과 연결된 짧은 보완 문장 (저/제 사용)."}}
  ],
  "prayer": ["주님,", "", "첫 번째 문장.", "두 번째 문장.", "", "..."]
}}"""


# ===== 2차 정제 프롬프트 (application만 검사/수정) =====
REFINE_SYSTEM_PROMPT = """당신은 한국 개신교 QT 묵상의 엄격한 편집자입니다.
신학적으로 균형 잡혀 있으며, 한국어 기독교 경건 표현에 정통합니다.
문제가 있는 부분만 최소한으로 수정하고, 문제가 없으면 원문을 그대로 유지합니다.
좋은 표현을 괜히 더 낫게 바꾸려 하지 않습니다."""


def build_refine_prompt(application: list, qt_data: dict) -> str:
    """2차 정제 프롬프트 — application 3개를 검사/수정"""
    verses_text = "\n".join(
        f"{v['number']} {v['text']}" for v in qt_data["verses"]
    )
    application_json = json.dumps(application, ensure_ascii=False, indent=2)

    return f"""아래 QT 묵상의 "말씀 적용" 3개를 검토하고, 규칙 위반만 수정해주세요.

[본문 참고용]
제목: {qt_data['title']}
구절: {qt_data['scripture_ref']}
본문:
{verses_text}

[원본 application]
{application_json}

[검사 규칙 — 위반 시에만 수정]

1. 위계적·시혜적 표현 금지 (가장 중요)
   독자를 '베푸는 자' 위치에 세우는 표현은 피합니다.
   ❌ "주변 사람에게 은혜를 베풀겠습니다" (시혜적)
   ❌ "~에게 전하/나누겠습니다" (시혜적)
   ❌ "이웃을 가르치겠습니다" (위계적)
   ✅ 허용 예: "사랑을 실천하겠습니다", "감사를 표현하겠습니다"
   → 시혜·위계 표현만 내면화 동사로 교체:
     "기억하겠습니다 / 알아차리겠습니다 / 붙들겠습니다 /
      놓치지 않겠습니다 / 머물겠습니다 / 응답하겠습니다"

2. 자기 낮춤 위반
   "나 / 내 / 나의 / 나를 / 나에게" → "저 / 제 / 저의 / 저를 / 저에게"

3. 보편 문구 위반
   아무 본문에나 들어갈 수 있는 문구는 본문 고유의 단어·장면으로 교체.
   (예: "작은 것에도 감사" → 본문 속 구체 표현으로)

4. 시작 구조 (다양성 — 반드시 확인)
   세 항목의 시작 단어가 서로 달라야 합니다.
   - 1번이 "저는 오늘,"으로 시작하지 않으면 → "저는 오늘, ~" 형태로 교체
   - 2·3번이 "저는 오늘,"으로 시작한다면 → 반드시 다른 시작으로 교체
     변주형 예시: "오늘부터, ~" / "이 말씀 앞에서, ~" / "주님, 제가 ~" /
                  "지금 제가 ~" / "이 본문이 보여주는 ~" / "말씀을 따라 ~" /
                  "하루를 열며, ~" / "주님의 마음으로, ~"
   - 2번과 3번의 시작도 서로 달라야 합니다.
   ※ 이 규칙이 지켜지지 않으면 세 적용이 평행 구조로 단조로워집니다.

[수정 원칙]
- 문제 없는 항목은 **그대로 유지**. 괜히 더 낫게 바꾸지 않습니다.
- 수정하더라도 원문의 따뜻한 톤과 본문 연결은 보존.
- 각 항목은 정확히 2문장 (statement + detail) 유지.

[좋은 예]
❌ 수정 전: "주변의 이웃에게 은혜를 나누겠습니다."
✅ 수정 후: "오늘 받은 은혜를 하루 내내 잊지 않겠습니다."

❌ 수정 전: "보아스의 마음을 배우겠습니다."
✅ 수정 후: "작은 이삭 하나에도 하나님의 손길이 스며 있음을 오늘 놓치지 않겠습니다."

JSON 형식으로 수정된 application 3개만 반환하세요:
{{
  "application": [
    {{"statement": "...", "detail": "..."}},
    {{"statement": "...", "detail": "..."}},
    {{"statement": "...", "detail": "..."}}
  ]
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
        "scenes": [
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
        "book_overview": {
            "author": "전통적으로 사무엘로 전해짐",
            "date": "사사 시대 이야기, 후대에 정리됨",
            "place": "이스라엘 백성을 위해 쓰였으며, 정확한 기록 장소는 알려져 있지 않습니다.",
            "core": "모압 여인 룻이 시어머니를 따라 베들레헴에 와 보아스와 가정을 이루는 이야기로, 평범한 삶 속에서 일하시는 하나님의 손길을 보여줍니다.",
        },
        "passage_intro": "오늘 본문은 이 거대한 이야기의 시작점입니다.",
        "verse_commentary": "'마라'는 히브리어로 '쓴맛'을 뜻합니다. 나오미는 자신의 고통을 숨기지 않고 솔직히 토로합니다. 그런데 본문 마지막에 '보리 추수가 시작될 때'라는 표현이 덧붙여집니다. 이는 단순한 시간 정보가 아닙니다. 비어 돌아온 그녀에게 다시 채우심이 시작될 것을 알리는 복선입니다.",
        "application": [
            {
                "statement": "저는 오늘, 쓰라린 감정을 숨기지 않겠습니다.",
                "detail": "'나를 마라라 부르라'는 본문의 솔직함을 제 기도에도 허락하겠습니다."
            },
            {
                "statement": "이 관계의 자리에서, 먼저 떠나지 않는 쪽이 되겠습니다.",
                "detail": "'어머니의 하나님이 나의 하나님'이라는 고백을 오늘 제 마음에 붙들겠습니다."
            },
            {
                "statement": "주님, 비어 돌아온 제 손에도 보리 추수의 때를 기다리게 하옵소서.",
                "detail": "본문 끝의 '보리 추수가 시작될 때'라는 작은 약속을 놓치지 않겠습니다."
            }
        ],
        "prayer": [
            "주님,",
            "룻이 낯선 밭에 서서",
            "이삭을 줍던 그 마음을 생각합니다.",
            "",
            "두렵지만 내딛었던 그 발걸음처럼,",
            "오늘 제가 선 낯선 자리에서도",
            "주님이 이미 예비하심을 믿게 하소서.",
            "",
            "작은 은혜에 감사하는 눈을 주시고,",
            "겸손히 손을 내밀게 하옵소서.",
            "",
            "예수님의 이름으로 기도합니다. 아멘."
        ]
    }


def _mock_generic(qt_data: dict) -> dict:
    """임의 날짜에도 동작하는 제네릭 샘플"""
    title = qt_data.get("title", "오늘의 말씀")
    book = qt_data.get("book_name", "성경")

    return {
        "scenes": [
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
        "book_overview": {
            "author": f"{book}의 저자에 대해서는 여러 견해가 있습니다",
            "date": f"{book}이 다루는 시대 이후 후대에 정리된 것으로 전해집니다",
            "place": "당시 하나님의 백성을 위해 기록되었습니다.",
            "core": f"{book}은 하나님과 그 백성 사이의 관계, 그 안에서 일하시는 하나님의 손길을 보여줍니다.",
        },
        "passage_intro": "오늘 본문은 이 책의 큰 흐름 속에서 특별한 위치를 차지합니다.",
        "verse_commentary": "오늘 본문에서 주목할 만한 표현들이 있습니다. 성경 원어의 뉘앙스와 당시 역사적 배경을 함께 살펴보면 본문이 더 깊이 이해됩니다. 하나님은 말씀을 통해 오늘도 우리에게 말씀하십니다.",
        "application": [
            {
                "statement": "저는 오늘, 이 본문이 가리키는 길을 한 걸음 따르겠습니다.",
                "detail": "본문의 핵심을 제 일상의 구체적 자리에 옮겨 담겠습니다."
            },
            {
                "statement": "이 말씀 앞에서, 숨겨왔던 제 태도 하나를 꺼내 놓겠습니다.",
                "detail": "본문의 한 장면을 제 오늘의 결정과 비교하겠습니다."
            },
            {
                "statement": "주님, 이 말씀이 저의 언어가 되게 하옵소서.",
                "detail": "본문 속 순종의 자세로 오늘 하루를 걷게 하소서."
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


# ===== 실제 API 호출 (2-pass) =====
def _calc_cost(usage) -> dict:
    """OpenAI usage 객체에서 비용 정보 계산"""
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


def _call_pass1(client, qt_data: dict) -> tuple:
    """1차: 전체 JSON 생성 (창의적 톤)"""
    user_prompt = build_user_prompt(qt_data)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    ai_data = json.loads(response.choices[0].message.content)
    cost = _calc_cost(response.usage)
    log(
        f"1차 토큰: {cost['total_tokens']} "
        f"(입력 {cost['input_tokens']} / 출력 {cost['output_tokens']}) "
        f"/ 비용: {cost['cost_krw']:.2f}원",
        "OK"
    )
    return ai_data, cost


def _call_pass2(client, application: list, qt_data: dict) -> tuple:
    """2차: application 3개만 검사/수정 (엄격한 편집자 톤)"""
    user_prompt = build_refine_prompt(application, qt_data)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REFINE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    result = json.loads(response.choices[0].message.content)
    refined = result.get("application")
    if not isinstance(refined, list) or len(refined) != 3:
        raise ValueError("2차 정제 결과 구조 오류: application이 3개 리스트가 아님")
    cost = _calc_cost(response.usage)
    log(
        f"2차 토큰: {cost['total_tokens']} "
        f"(입력 {cost['input_tokens']} / 출력 {cost['output_tokens']}) "
        f"/ 비용: {cost['cost_krw']:.2f}원",
        "OK"
    )
    return refined, cost


def generate_real(qt_data: dict) -> tuple:
    """OpenAI API로 2-pass 생성. (ai_data, cost_info) 튜플 반환.

    1차: 전체 콘텐츠 생성 (temperature=0.7, 창의적)
    2차: application 3개만 검사·수정 (temperature=0.3, 엄격)
    """
    try:
        from openai import OpenAI
    except ImportError:
        log("openai 라이브러리가 설치되지 않았습니다.", "ERR")
        log("설치: pip install openai python-dotenv")
        raise

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

    # ===== Pass 1: 전체 생성 =====
    log(f"1차 생성 중 (모델: {MODEL}, temperature=0.7)...")
    ai_data, cost_1 = _call_pass1(client, qt_data)

    # ===== Pass 2: application 정제 =====
    log("2차 application 정제 중 (temperature=0.3)...")
    zero_cost = {
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        "cost_usd": 0, "cost_krw": 0,
    }
    try:
        refined_app, cost_2 = _call_pass2(client, ai_data["application"], qt_data)
        ai_data["application"] = refined_app
    except Exception as e:
        log(f"2차 정제 실패, 1차 결과 그대로 사용: {e}", "WARN")
        cost_2 = zero_cost

    # ===== 비용 합산 =====
    cost_info = {
        "input_tokens": cost_1["input_tokens"] + cost_2["input_tokens"],
        "output_tokens": cost_1["output_tokens"] + cost_2["output_tokens"],
        "total_tokens": cost_1["total_tokens"] + cost_2["total_tokens"],
        "cost_usd": round(cost_1["cost_usd"] + cost_2["cost_usd"], 6),
        "cost_krw": round(cost_1["cost_krw"] + cost_2["cost_krw"], 2),
        "breakdown": {"pass1": cost_1, "pass2": cost_2},
    }

    log(
        f"합계 토큰: {cost_info['total_tokens']} "
        f"/ 비용: ${cost_info['cost_usd']:.6f} (약 {cost_info['cost_krw']:.2f}원)",
        "OK"
    )

    return ai_data, cost_info


# ===== 검증 =====
def validate(ai_data: dict) -> list:
    """AI_PROMPT.md 기준으로 검증. 경고 리스트 반환."""
    warnings = []

    # scenes: 5개
    scenes = ai_data.get("scenes", [])
    if len(scenes) != 5:
        warnings.append(f"scenes가 정확히 5개가 아님 (현재 {len(scenes)}개)")

    # book_overview 검증: 객체(4필드)이며 옛 문자열도 폴백으로 허용
    bo = ai_data.get("book_overview")
    if not bo:
        warnings.append("book_overview 필드 없음")
    elif isinstance(bo, dict):
        for key in ("author", "date", "place", "core"):
            if not bo.get(key):
                warnings.append(f"book_overview.{key} 비어 있음")
    elif isinstance(bo, str):
        if len(bo) < 30:
            warnings.append(f"book_overview 문자열이 너무 짧음 ({len(bo)}자)")

    # passage_intro 존재 확인
    if not ai_data.get("passage_intro"):
        warnings.append("passage_intro 필드 없음")

    # characters: 1~3명
    chars = ai_data.get("characters", [])
    if not (1 <= len(chars) <= 3):
        warnings.append(f"characters가 1~3명 범위를 벗어남 (현재 {len(chars)}명)")

    # application: 정확히 3개
    app = ai_data.get("application", [])
    if len(app) != 3:
        warnings.append(f"application이 정확히 3개가 아님 (현재 {len(app)}개)")

    # prayer: 10~13줄 (빈 줄 포함)
    prayer = ai_data.get("prayer", [])
    if not (10 <= len(prayer) <= 13):
        warnings.append(f"prayer가 10~13줄 범위를 벗어남 (현재 {len(prayer)}줄)")

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
    log(f"장면:     {len(ai_data.get('scenes', []))}개")
    log(f"인물:     {len(ai_data.get('characters', []))}명")
    log(f"적용:     {len(ai_data.get('application', []))}개")
    log(f"기도문:   {len(ai_data.get('prayer', []))}줄")
    log("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
