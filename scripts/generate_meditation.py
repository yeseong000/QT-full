"""
5단 호흡 묵상 생성기 (장면·질문·맥락·통찰·연결)
=====================================================
오륜교회 주만나 QT JSON과 5단 호흡 시스템 프롬프트 + fewshot 5개를 입력받아
GPT-4o-mini로 18~22줄 분량의 묵상 카드 콘텐츠를 생성합니다.

생성 결과는 기존 generate_ai.py 결과(data/ai/{date}.json)와 충돌하지 않도록
별도 디렉토리 data/deep_dive/{date}.json 에 저장합니다.

사용법:
    # 기본 (오늘 날짜)
    python scripts/generate_meditation.py

    # 특정 날짜 (positional)
    python scripts/generate_meditation.py 2026-05-09

    # 특정 날짜 (--date 플래그, 기존 generate_ai.py와 호환)
    python scripts/generate_meditation.py --date 2026-05-09

    # 저장하지 않고 결과만 출력
    python scripts/generate_meditation.py 2026-05-09 --dry-run

    # 이미 결과 파일이 있어도 강제 재생성
    python scripts/generate_meditation.py 2026-05-09 --force

필요 환경:
    pip install openai python-dotenv
    .env 파일에 OPENAI_API_KEY 설정

월간 비용 추정 (gpt-4o-mini, 입력 $0.15/1M · 출력 $0.60/1M, 환율 1500원):
    - 시스템 프롬프트(~8,000) + fewshot 5개(~4,000) + 오늘 입력(~600) = 입력 ~12,600 토큰
    - 출력(~1,200 토큰) → 1회 약 $0.0026 ≈ 3.9원
    - 매일 1회 × 30일 = 월 약 $0.078 ≈ 117원
    - prompt caching 적용 시 월 약 60~70원으로 감소 가능
    - generate_ai.py(2-pass, 약 51원/월)와 합산해 전체 GPT 비용 월 ~170원

종료 코드:
    0 = 성공 / 정상 skip
    1 = 입력 누락 (qt 파일, 시스템 프롬프트, fewshot, OPENAI_API_KEY)
    2 = API 호출 실패 (1회 재시도 후에도)
    3 = JSON 파싱 실패
    4 = 검증 실패 (5개 키 중 누락 또는 빈 값)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ===== 설정 =====
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
QT_DIR = PROJECT_ROOT / "data" / "qt"
DEEP_DIVE_DIR = PROJECT_ROOT / "data" / "deep_dive"
REF_DIR = PROJECT_ROOT / "data" / "reference"
PROMPT_DIR = PROJECT_ROOT / "prompts" / "breath_5step"
SYSTEM_PROMPT_PATH = PROMPT_DIR / "_final_system.md"
FEWSHOT_PATH = PROMPT_DIR / "breath_5step_examples.json"

FOLLOW_UP_PROMPT_PATH = PROJECT_ROOT / "prompts" / "follow_up" / "system.md"

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.7
MAX_TOKENS = 1500

FOLLOW_UP_TEMPERATURE = 0.8
FOLLOW_UP_MAX_TOKENS = 6000   # v3: 메인 3 + 꼬리 6 = 9 답변 × ~400자 ≈ 5400 토큰

# 가격 (2026년 기준, 백만 토큰당 USD)
PRICE_INPUT_PER_1M = 0.15
PRICE_OUTPUT_PER_1M = 0.60
USD_TO_KRW = 1500

REQUIRED_KEYS = ["장면", "질문", "맥락", "통찰", "연결"]


# ===== 로깅 =====
def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now(KST).strftime("%H:%M:%S")
    prefix = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "SKIP": "⏭️ "}.get(level, "• ")
    print(f"[{now}] {prefix} {msg}")


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


# ===== 입력 로더 =====
def load_prompt_assets() -> tuple[str, list]:
    """시스템 프롬프트와 fewshot 예시를 로드합니다."""
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"시스템 프롬프트 파일을 찾을 수 없습니다: {SYSTEM_PROMPT_PATH}\n"
            f"prompts/breath_5step/_final_system.md를 먼저 작성해주세요."
        )
    if not FEWSHOT_PATH.exists():
        raise FileNotFoundError(
            f"fewshot 예시 파일을 찾을 수 없습니다: {FEWSHOT_PATH}\n"
            f"prompts/breath_5step/breath_5step_examples.json을 먼저 작성해주세요."
        )

    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    fewshot = json.loads(FEWSHOT_PATH.read_text(encoding="utf-8"))

    if not isinstance(fewshot, list) or not fewshot:
        raise ValueError(
            f"fewshot 파일이 비어있거나 리스트 형식이 아닙니다: {FEWSHOT_PATH}"
        )
    return system_prompt, fewshot


def load_qt_data(date_str: str) -> dict:
    """data/qt/{date}.json 로드."""
    qt_path = QT_DIR / f"{date_str}.json"
    if not qt_path.exists():
        raise FileNotFoundError(
            f"{qt_path}를 찾을 수 없습니다. "
            f"먼저 fetch_qt.py를 실행해 QT 데이터를 준비해주세요."
        )
    return json.loads(qt_path.read_text(encoding="utf-8"))


def load_kb(book_name: str) -> dict | None:
    """data/reference/{book}.json이 있을 때만 로드. 없으면 None."""
    if not book_name:
        return None
    ref_path = REF_DIR / f"{book_name}.json"
    if not ref_path.exists():
        return None
    try:
        return json.loads(ref_path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"KB 로드 실패 ({ref_path}): {e}", "WARN")
        return None


# ===== 입력 변환 =====
def build_user_payload(qt_data: dict, kb: dict | None, focus_question: str | None = None) -> dict:
    """QT 데이터를 시스템 프롬프트가 기대하는 한글 필드 형식으로 변환.

    focus_question이 주어지면 그 질문 하나에 집중하도록 오륜_질문을 좁히고,
    '연결' 단계가 그 질문을 자연스럽게 떠올리게 하라는 집중_지시를 덧붙인다.
    (시스템 프롬프트는 건드리지 않으므로 기존 출력 형식·검증 규칙은 그대로 유지)
    """
    body_text = "\n".join(
        f"{v['number']} {v['text']}" for v in qt_data.get("verses", [])
    )
    payload = {
        "본문_참조": qt_data.get("scripture_ref", ""),
        "본문_제목": qt_data.get("title", ""),
        "본문_내용": body_text,
        "오륜_질문": qt_data.get("oryun_questions", []),
        "지식": kb,
    }
    if focus_question:
        payload["오륜_질문"] = [focus_question]
        payload["집중_지시"] = (
            "이번 묵상은 위 '오륜_질문' 하나와 자연스럽게 이어지도록 만들어주세요. "
            "특히 마지막 '연결' 단계가 이 질문을 스스로 떠올리게 하는 적용으로 마무리되게 하세요. "
            "단, 질문을 그대로 인용하지 말고 본문에서 우러나오도록 풀어주세요."
        )
    return payload


def build_messages(system_prompt: str, fewshot: list, payload: dict) -> list:
    """OpenAI Chat Completions용 messages 배열 구성."""
    messages = [{"role": "system", "content": system_prompt}]
    for ex in fewshot:
        if "input" not in ex or "output" not in ex:
            log(f"fewshot 항목에 input/output 키가 없습니다 (스킵): {ex.get('_label', '?')}", "WARN")
            continue
        messages.append({
            "role": "user",
            "content": json.dumps(ex["input"], ensure_ascii=False),
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(ex["output"], ensure_ascii=False),
        })
    messages.append({
        "role": "user",
        "content": json.dumps(payload, ensure_ascii=False),
    })
    return messages


# ===== API 호출 =====
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


def call_openai(messages: list, max_retries: int = 1, *, temperature: float = TEMPERATURE, max_tokens: int = MAX_TOKENS, response_format: dict | None = None):
    """OpenAI API 호출 — 실패 시 1회 재시도. response_format으로 스키마 강제 가능."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "openai 라이브러리가 설치되지 않았습니다. "
            "pip install openai python-dotenv"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY가 없습니다. .env 파일에 추가하거나 환경변수로 설정해주세요."
        )

    rf = response_format if response_format is not None else {"type": "json_object"}
    client = OpenAI(api_key=api_key)
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=rf,
            )
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                log(f"API 호출 실패, 2초 후 재시도 ({attempt + 1}/{max_retries}): {e}", "WARN")
                time.sleep(2)
    raise RuntimeError(f"API 호출 최종 실패: {last_err}")


# ===== 더 깊이 묻기 (Follow-up Q&A) =====
def generate_follow_up(qt_data: dict, kb: dict | None, deep_dive: dict) -> tuple[list, dict] | tuple[None, None]:
    """
    5단 호흡 묵상 직후 호출되는 2차 생성기.
    본문에서 떠올릴 만한 파생 질문 3개 + 깊이 있는 답변 3개를 만듭니다.

    반환: (follow_up_questions list, cost_info dict) — 실패 시 (None, None)
    """
    if not FOLLOW_UP_PROMPT_PATH.exists():
        log(f"follow-up 시스템 프롬프트가 없습니다: {FOLLOW_UP_PROMPT_PATH} → 건너뜀", "WARN")
        return None, None

    try:
        system_prompt = FOLLOW_UP_PROMPT_PATH.read_text(encoding="utf-8")
        body_text = "\n".join(
            f"{v['number']} {v['text']}" for v in qt_data.get("verses", [])
        )
        payload = {
            "본문_참조": qt_data.get("scripture_ref", ""),
            "본문_제목": qt_data.get("title", ""),
            "본문_내용": body_text,
            "오륜_질문": qt_data.get("oryun_questions", []),
            "지식": kb,
            "이미_다룬_5단": {
                "장면": deep_dive.get("장면", ""),
                "질문": deep_dive.get("질문", ""),
                "맥락": deep_dive.get("맥락", ""),
                "통찰": deep_dive.get("통찰", ""),
                "연결": deep_dive.get("연결", ""),
            },
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        # OpenAI Structured Output — follow_ups 배열을 스키마로 강제
        schema = {
            "type": "object",
            "properties": {
                "follow_up_questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"},
                            "follow_ups": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "question": {"type": "string"},
                                        "answer": {"type": "string"},
                                    },
                                    "required": ["question", "answer"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["question", "answer", "follow_ups"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["follow_up_questions"],
            "additionalProperties": False,
        }
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "follow_up_questions_response",
                "strict": True,
                "schema": schema,
            },
        }

        response = call_openai(
            messages,
            max_retries=1,
            temperature=FOLLOW_UP_TEMPERATURE,
            max_tokens=FOLLOW_UP_MAX_TOKENS,
            response_format=response_format,
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        items = parsed.get("follow_up_questions", [])

        # 검증: 메인 3개 + 각 메인의 꼬리 2개, 모두 question/answer 채워짐
        if not isinstance(items, list) or len(items) != 3:
            log(f"follow-up 검증 실패: 메인 배열 길이 {len(items) if isinstance(items, list) else 'N/A'} (3 기대) → 건너뜀", "WARN")
            return None, None
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                log(f"follow-up 검증 실패: 메인[{i}]가 dict 아님 → 건너뜀", "WARN")
                return None, None
            q = item.get("question", "").strip() if isinstance(item.get("question"), str) else ""
            a = item.get("answer", "").strip() if isinstance(item.get("answer"), str) else ""
            if not q or not a:
                log(f"follow-up 검증 실패: 메인[{i}]의 question/answer 비어있음 → 건너뜀", "WARN")
                return None, None
            # 꼬리 검증
            follow_ups = item.get("follow_ups")
            if not isinstance(follow_ups, list) or len(follow_ups) != 2:
                log(f"follow-up 검증 실패: 메인[{i}]의 꼬리 배열 길이 {len(follow_ups) if isinstance(follow_ups, list) else 'N/A'} (2 기대) → 건너뜀", "WARN")
                return None, None
            for j, fu in enumerate(follow_ups):
                if not isinstance(fu, dict):
                    log(f"follow-up 검증 실패: 메인[{i}].꼬리[{j}]가 dict 아님 → 건너뜀", "WARN")
                    return None, None
                fq = fu.get("question", "").strip() if isinstance(fu.get("question"), str) else ""
                fa = fu.get("answer", "").strip() if isinstance(fu.get("answer"), str) else ""
                if not fq or not fa:
                    log(f"follow-up 검증 실패: 메인[{i}].꼬리[{j}]의 question/answer 비어있음 → 건너뜀", "WARN")
                    return None, None

        cost_info = calc_cost(response.usage)
        return items, cost_info
    except Exception as e:
        log(f"follow-up 생성 실패 (1차 묵상은 유지): {e}", "WARN")
        return None, None


# ===== 검증 =====
def validate(deep_dive: dict) -> list[str]:
    """5개 키 모두 존재 + 비어있지 않은지 확인. 문제 항목 리스트 반환."""
    issues: list[str] = []
    for key in REQUIRED_KEYS:
        value = deep_dive.get(key)
        if value is None:
            issues.append(f"키 누락: '{key}'")
        elif not isinstance(value, str):
            issues.append(f"'{key}'가 문자열이 아님 (타입: {type(value).__name__})")
        elif not value.strip():
            issues.append(f"'{key}'가 빈 문자열")
    return issues


# ===== 저장 =====
def save_json(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


# ===== 본문 순서(앞/뒤) 분할 플래너 =====
PASSAGE_SPLIT_SYSTEM = """당신은 성경 본문을 묵상 단위로 나누는 편집자입니다.
주어진 본문을 '자연스러운 장면 전환점'을 기준으로 정확히 2개의 연속 구간으로 나누세요.

규칙:
- 두 구간은 서로 겹치지 않고, 본문 전체를 빠짐없이 덮어야 합니다 (앞 구간 끝절 + 1 = 뒤 구간 첫절).
- 인물·사건·장소가 바뀌는 지점에서 끊으세요. 절 수를 기계적으로 절반 내지 마세요.
- 다만 두 구간의 분량이 지나치게 치우치지 않게 균형을 맞추세요(한쪽이 한두 절만 남지 않도록). 가장 자연스러운 전환점을 우선하되, 비슷한 분량으로 나눌 수 있는 전환점을 고르세요.
- 각 구간의 '소주제'와 '교훈축'을 각각 한 줄로 쓰되, 두 구간의 교훈축은 서로 확실히 다른 측면이어야 합니다 (겹침 절대 금지).
- 큰 주제는 유지하되, 앞 구간과 뒤 구간이 그 주제의 '서로 다른 면'을 비추게 하세요.

출력은 아래 JSON만 (설명·군더더기 금지):
{"segments":[{"verse_start":정수,"verse_end":정수,"소주제":"한 줄","교훈축":"한 줄"},{"verse_start":정수,"verse_end":정수,"소주제":"한 줄","교훈축":"한 줄"}]}
"""


def plan_passage_split(qt_data: dict) -> tuple[list, dict] | tuple[None, None]:
    """본문을 앞/뒤 2구간으로 나누고 각 구간의 소주제·교훈축을 결정. (segments, cost) 반환."""
    verses = qt_data.get("verses", [])
    if len(verses) < 2:
        log("본문 절 수가 너무 적어 앞/뒤 분할이 불가합니다.", "ERR")
        return None, None
    body_text = "\n".join(f"{v['number']} {v['text']}" for v in verses)
    payload = {
        "본문_참조": qt_data.get("scripture_ref", ""),
        "본문_제목": qt_data.get("title", ""),
        "본문_내용": body_text,
    }
    messages = [
        {"role": "system", "content": PASSAGE_SPLIT_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        response = call_openai(
            messages,
            max_retries=1,
            temperature=0.4,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
    except RuntimeError as e:
        log(f"분할 플래너 호출 실패: {e}", "ERR")
        return None, None

    try:
        parsed = json.loads(response.choices[0].message.content)
        segments = parsed.get("segments", [])
    except json.JSONDecodeError as e:
        log(f"분할 플래너 JSON 파싱 실패: {e}", "ERR")
        return None, None

    # 검증: 2구간, 연속·비겹침, 본문 전체 커버
    nums = [v["number"] for v in verses]
    vmin, vmax = min(nums), max(nums)
    if not isinstance(segments, list) or len(segments) != 2:
        log(f"분할 결과가 2구간이 아닙니다 (받음: {len(segments) if isinstance(segments, list) else 'N/A'})", "ERR")
        return None, None
    try:
        s0, e0 = int(segments[0]["verse_start"]), int(segments[0]["verse_end"])
        s1, e1 = int(segments[1]["verse_start"]), int(segments[1]["verse_end"])
    except (KeyError, ValueError, TypeError):
        log("분할 결과에 verse_start/verse_end 정수가 없습니다.", "ERR")
        return None, None
    if not (s0 == vmin and e1 == vmax and s1 == e0 + 1 and s0 <= e0 < s1 <= e1):
        log(f"분할 범위가 연속·전체커버 규칙을 어겼습니다: [{s0}-{e0}] / [{s1}-{e1}] (본문 {vmin}-{vmax})", "WARN")
        # 규칙 위반 시 기계적 절반으로 보정 (안전망)
        mid = nums[len(nums) // 2 - 1]
        segments[0]["verse_start"], segments[0]["verse_end"] = vmin, mid
        segments[1]["verse_start"], segments[1]["verse_end"] = nums[len(nums) // 2], vmax
        log(f"→ 절반 분할로 보정: [{vmin}-{mid}] / [{nums[len(nums)//2]}-{vmax}]", "INFO")

    cost_info = calc_cost(response.usage)
    return segments, cost_info


def build_segment_payload(qt_data: dict, kb: dict | None, segment: dict, avoid_lesson: str | None = None) -> dict:
    """특정 구간(앞/뒤)만 다루는 5단 호흡 user payload 구성. 본문 순서 분할 모드 전용.

    오륜 질문은 묵상에 끌어오지 않음(연동 제거). step 4 질문 데이터는 qt에 그대로 남아 있음.
    avoid_lesson이 있으면 앞 구간 교훈을 반복하지 않도록 지시.
    """
    vs, ve = int(segment["verse_start"]), int(segment["verse_end"])
    seg_verses = [v for v in qt_data.get("verses", []) if vs <= v.get("number", -1) <= ve]
    seg_body = "\n".join(f"{v['number']} {v['text']}" for v in seg_verses)
    instruction = (
        "이 묵상은 위 '본문_내용'(이 구간)만 다루세요. 다른 구간의 사건·교훈을 절대 끌어오지 마세요. "
        "'구간_교훈축'을 중심으로 5단 호흡을 전개하고, 큰 주제는 유지하되 이 구간만의 면을 비추세요."
    )
    payload = {
        "본문_참조": qt_data.get("scripture_ref", ""),
        "본문_제목": qt_data.get("title", ""),
        "본문_내용": seg_body,
        "구간_범위": f"{vs}-{ve}",
        "구간_소주제": segment.get("소주제", ""),
        "구간_교훈축": segment.get("교훈축", ""),
        "집중_지시": instruction,
        "지식": kb,
    }
    if avoid_lesson:
        payload["이미_다룬_교훈"] = avoid_lesson
        payload["겹침_금지"] = (
            "위 '이미_다룬_교훈'은 앞 구간이 이미 다룬 내용이에요. "
            "절대 같은 교훈을 반복하지 말고, 이 구간만의 다른 교훈을 뽑으세요."
        )
    return payload


# ===== 5단 호흡 1회 생성 (단일/변형 공용) =====
def generate_meditation_once(
    system_prompt: str,
    fewshot: list,
    qt_data: dict,
    kb: dict | None,
    focus_question: str | None = None,
    payload: dict | None = None,
) -> tuple[dict, dict] | tuple[None, None]:
    """5단 호흡 한 세트를 생성. 성공 시 (5키 dict, cost dict), 실패 시 (None, None).

    payload를 직접 주면 그대로 사용(본문 순서 분할 등), 없으면 focus_question으로 구성.
    """
    if payload is None:
        payload = build_user_payload(qt_data, kb, focus_question)
    messages = build_messages(system_prompt, fewshot, payload)

    try:
        response = call_openai(messages, max_retries=1)
    except RuntimeError as e:
        log(str(e), "ERR")
        return None, None

    raw_content = response.choices[0].message.content
    try:
        deep_dive = json.loads(raw_content)
    except json.JSONDecodeError as e:
        log(f"응답 JSON 파싱 실패: {e}", "ERR")
        log(f"원본 응답 일부: {raw_content[:200]}...", "WARN")
        return None, None

    issues = validate(deep_dive)
    if issues:
        for issue in issues:
            log(issue, "ERR")
        log("검증 실패 — 응답 형식이 시스템 프롬프트 요구를 충족하지 않습니다.", "ERR")
        return None, None

    cost_info = calc_cost(response.usage)
    return deep_dive, cost_info


# ===== 메인 =====
def main() -> int:
    parser = argparse.ArgumentParser(description="5단 호흡 묵상 생성기")
    parser.add_argument(
        "date_pos",
        nargs="?",
        default=None,
        help="처리할 날짜 (YYYY-MM-DD). 생략 시 오늘.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="처리할 날짜 (positional 인자 대신 사용 가능).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="저장하지 않고 결과만 출력.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="결과 파일이 이미 있어도 재생성.",
    )
    parser.add_argument(
        "--variants",
        action="store_true",
        help="오륜 질문 2개 각각에 집중한 5단 호흡 2세트를 생성해 variants 배열로 저장.",
    )
    parser.add_argument(
        "--passage",
        action="store_true",
        help="본문을 앞/뒤 2구간으로 나눠(AI가 장면 전환점 결정) 교훈이 겹치지 않는 5단 호흡 2세트를 생성.",
    )
    args = parser.parse_args()

    # .env 로드
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        log("python-dotenv 미설치. 환경변수를 직접 사용합니다.", "WARN")

    date_str = args.date_pos or args.date or today_str()

    log("=" * 50)
    log(f"5단 호흡 묵상 생성 시작 (날짜: {date_str})")
    log("=" * 50)

    # 0. 멱등성 체크
    output_path = DEEP_DIVE_DIR / f"{date_str}.json"
    if output_path.exists() and not args.force and not args.dry_run:
        log(f"결과 파일이 이미 있습니다 → 건너뜁니다: {output_path.name}", "SKIP")
        log("재생성하려면 --force 옵션을 사용해주세요.")
        return 0

    # 1. 입력 로드
    try:
        system_prompt, fewshot = load_prompt_assets()
        qt_data = load_qt_data(date_str)
        kb = load_kb(qt_data.get("book_name", ""))
        log(
            f"QT 데이터: {qt_data.get('title')} ({qt_data.get('scripture_ref')})",
            "OK",
        )
        log(
            f"fewshot 예시: {len(fewshot)}개 / KB: {'있음' if kb else '없음'}",
            "OK",
        )
    except (FileNotFoundError, ValueError) as e:
        log(str(e), "ERR")
        return 1

    # 2. 생성 모드 결정
    oryun_questions = qt_data.get("oryun_questions", []) or []
    variants: list[dict] = []
    total_cost = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "cost_krw": 0.0}

    if args.passage:
        # === 본문 순서(앞/뒤) 분할 모드 ===
        log("본문 앞/뒤 분할 플래너 실행 중...", "INFO")
        segments, plan_cost = plan_passage_split(qt_data)
        if not segments:
            log("본문 분할 실패 — 중단합니다.", "ERR")
            return 2
        for k in total_cost:
            total_cost[k] = round(total_cost[k] + plan_cost[k], 6)
        for s in segments:
            log(f"  · {s['verse_start']}-{s['verse_end']}절 / 교훈축: {s.get('교훈축', '')[:40]}", "OK")

        prev_lesson = None
        for idx, seg in enumerate(segments):
            label = f"{'앞' if idx == 0 else '뒤'}부분({seg['verse_start']}-{seg['verse_end']})"
            log(f"[{label}] 5단 호흡 생성 중...", "INFO")
            payload = build_segment_payload(qt_data, kb, seg, avoid_lesson=prev_lesson)
            deep_dive, cost_info = generate_meditation_once(system_prompt, fewshot, qt_data, kb, payload=payload)
            if deep_dive is None:
                log(f"[{label}] 생성 실패 — 중단합니다.", "ERR")
                return 2
            log(f"[{label}] 토큰 {cost_info['total_tokens']} / 비용 약 {cost_info['cost_krw']:.2f}원", "OK")
            for k in total_cost:
                total_cost[k] = round(total_cost[k] + cost_info[k], 6)
            variant = {key: deep_dive[key] for key in REQUIRED_KEYS}
            variant["구간"] = f"{seg['verse_start']}-{seg['verse_end']}"
            variant["소주제"] = seg.get("소주제", "")
            variant["scene_image"] = f"{date_str}.png" if idx == 0 else f"{date_str}-{idx + 1}.png"
            variants.append(variant)
            # 다음 구간이 같은 교훈을 반복하지 않도록 이번 통찰+연결을 넘김
            prev_lesson = f"통찰: {deep_dive['통찰']}\n연결: {deep_dive['연결']}"
    else:
        # === 질문별 / 단일 모드 (기존) ===
        if args.variants:
            if len(oryun_questions) < 2:
                log(
                    f"--variants는 오륜 질문이 2개 이상 필요합니다 (현재 {len(oryun_questions)}개). "
                    "단일 묵상으로 진행합니다.",
                    "WARN",
                )
                focus_questions = [None]
            else:
                focus_questions = oryun_questions[:2]
        else:
            focus_questions = [None]

        for idx, fq in enumerate(focus_questions):
            label = f"변형 {idx + 1}/{len(focus_questions)}" if len(focus_questions) > 1 else "단일"
            log(f"[{label}] 5단 호흡 생성 중...{(' (집중 질문: ' + fq[:30] + '…)') if fq else ''}", "INFO")
            deep_dive, cost_info = generate_meditation_once(system_prompt, fewshot, qt_data, kb, focus_question=fq)
            if deep_dive is None:
                log(f"[{label}] 생성 실패 — 중단합니다.", "ERR")
                return 2
            log(
                f"[{label}] 토큰 {cost_info['total_tokens']} / 비용 약 {cost_info['cost_krw']:.2f}원",
                "OK",
            )
            for k in total_cost:
                total_cost[k] = round(total_cost[k] + cost_info[k], 6)
            variant = {key: deep_dive[key] for key in REQUIRED_KEYS}
            if fq:
                variant["오륜질문"] = fq
            # 장면 이미지 파일명: 첫 변형은 기존 경로({date}.png), 이후는 {date}-N.png
            variant["scene_image"] = f"{date_str}.png" if idx == 0 else f"{date_str}-{idx + 1}.png"
            variants.append(variant)

    # 4. 더 깊이 묻기 (Follow-up Q&A) — variants[0] 기준 1회만 (실패해도 본 묵상은 살림)
    log("더 깊이 묻기 생성 중...", "INFO")
    follow_up_items, follow_up_cost = generate_follow_up(qt_data, kb, variants[0])
    if follow_up_items:
        log(
            f"더 깊이 묻기 OK · 토큰: {follow_up_cost['total_tokens']} / 비용: 약 {follow_up_cost['cost_krw']:.2f}원",
            "OK",
        )
    else:
        log("더 깊이 묻기 생성 건너뜀 (5단 호흡은 정상 저장됨)", "WARN")

    # 5. 메타데이터 조립 — 최상위 5키 = variants[0] (하위 호환)
    result = {
        "date": date_str,
        "scripture_ref": qt_data.get("scripture_ref", ""),
        "title": qt_data.get("title", ""),
        **{key: variants[0][key] for key in REQUIRED_KEYS},
        "generated_at": datetime.now(KST).isoformat(),
        "model": MODEL,
        "_cost": total_cost,
    }
    # 변형이 2개 이상일 때만 variants 배열을 기록 (단일 날짜는 기존 스키마 그대로)
    if len(variants) > 1:
        result["variants"] = variants
    if follow_up_items:
        result["follow_up_questions"] = follow_up_items
        result["_cost_followup"] = follow_up_cost

    # 6. 저장
    if args.dry_run:
        log("[DRY RUN] 저장 생략 — 결과를 stdout에 출력합니다.")
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))
    else:
        save_json(result, output_path)
        log(f"저장 완료: {output_path}", "OK")

    log("=" * 50)
    for vi, variant in enumerate(variants):
        if len(variants) > 1:
            log(f"--- 변형 {vi + 1} ({variant['scene_image']}) ---")
        for key in REQUIRED_KEYS:
            line_count = variant[key].count("\n") + 1
            log(f"{key}: {line_count}줄")
    log("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
