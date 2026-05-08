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

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.7
MAX_TOKENS = 1500

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
def build_user_payload(qt_data: dict, kb: dict | None) -> dict:
    """QT 데이터를 시스템 프롬프트가 기대하는 한글 필드 형식으로 변환."""
    body_text = "\n".join(
        f"{v['number']} {v['text']}" for v in qt_data.get("verses", [])
    )
    return {
        "본문_참조": qt_data.get("scripture_ref", ""),
        "본문_제목": qt_data.get("title", ""),
        "본문_내용": body_text,
        "오륜_질문": qt_data.get("oryun_questions", []),
        "지식": kb,
    }


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


def call_openai(messages: list, max_retries: int = 1):
    """OpenAI API 호출 — 실패 시 1회 재시도."""
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

    client = OpenAI(api_key=api_key)
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                log(f"API 호출 실패, 2초 후 재시도 ({attempt + 1}/{max_retries}): {e}", "WARN")
                time.sleep(2)
    raise RuntimeError(f"API 호출 최종 실패: {last_err}")


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

    # 2. 메시지 구성
    payload = build_user_payload(qt_data, kb)
    messages = build_messages(system_prompt, fewshot, payload)

    # 3. API 호출
    try:
        response = call_openai(messages, max_retries=1)
    except RuntimeError as e:
        msg = str(e)
        if "OPENAI_API_KEY" in msg or "openai 라이브러리" in msg:
            log(msg, "ERR")
            return 1
        log(msg, "ERR")
        return 2

    # 4. JSON 파싱
    raw_content = response.choices[0].message.content
    try:
        deep_dive = json.loads(raw_content)
    except json.JSONDecodeError as e:
        log(f"응답 JSON 파싱 실패: {e}", "ERR")
        log(f"원본 응답 일부: {raw_content[:200]}...", "WARN")
        return 3

    # 5. 검증
    issues = validate(deep_dive)
    if issues:
        for issue in issues:
            log(issue, "ERR")
        log("검증 실패 — 응답 형식이 시스템 프롬프트 요구를 충족하지 않습니다.", "ERR")
        return 4

    cost_info = calc_cost(response.usage)
    log(
        f"토큰: {cost_info['total_tokens']} "
        f"(입력 {cost_info['input_tokens']} / 출력 {cost_info['output_tokens']}) "
        f"/ 비용: ${cost_info['cost_usd']:.6f} (약 {cost_info['cost_krw']:.2f}원)",
        "OK",
    )

    # 6. 메타데이터 추가
    result = {
        "date": date_str,
        "scripture_ref": qt_data.get("scripture_ref", ""),
        "title": qt_data.get("title", ""),
        "장면": deep_dive["장면"],
        "질문": deep_dive["질문"],
        "맥락": deep_dive["맥락"],
        "통찰": deep_dive["통찰"],
        "연결": deep_dive["연결"],
        "generated_at": datetime.now(KST).isoformat(),
        "model": MODEL,
        "_cost": cost_info,
    }

    # 7. 저장
    if args.dry_run:
        log("[DRY RUN] 저장 생략 — 결과를 stdout에 출력합니다.")
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))
    else:
        save_json(result, output_path)
        log(f"저장 완료: {output_path}", "OK")

    log("=" * 50)
    for key in REQUIRED_KEYS:
        line_count = result[key].count("\n") + 1
        log(f"{key}: {line_count}줄")
    log("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
