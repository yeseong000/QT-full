"""
오늘의 장면 일러스트 생성기 (gpt-image-1)
==========================================
매일 본문이 바뀌므로, 회원님이 손으로 쓰시던 이미지 프롬프트를 자동화합니다.

흐름 (회원님의 프롬프트 공식을 그대로 자동화):
    1) data/deep_dive/{date}.json + data/qt/{date}.json 로드
       → ①본문 구절 ②주제 ③본문 따라가기(5단 호흡) 확보
    2) GPT(text)로 "현재 상황 브리프" 생성  ← 회원님이 손으로 쓰던 ④번
       → {인물(행동·표정), 배경(낮은 디테일·상징 표식), 분위기}
    3) 최종 이미지 프롬프트 = style.md(고정 화풍) + ①②③ + ④브리프
    4) gpt-image-1 호출. 참고 일러스트(src/images/참고 일러스트.png)를 항상 첨부해
       화풍을 고정한 채 그날 장면만 그림.
    5) src/images/scenes/{date}.png 로 저장 → step-2 페이지가 자동 노출

사용법:
    python scripts/generate_scene_image.py                 # 오늘
    python scripts/generate_scene_image.py 2026-06-03      # 특정 날짜
    python scripts/generate_scene_image.py --force         # 이미 있어도 재생성
    python scripts/generate_scene_image.py --dry-run       # 이미지 생성 없이 프롬프트만 출력(무료)

필요 환경:
    pip install openai python-dotenv
    .env 에 OPENAI_API_KEY

비용 (gpt-image-1, 2026년 기준 대략):
    - 브리프(text, gpt-4o-mini): 1회 약 1~2원
    - 이미지 1장: quality "medium" · 1536x1024 → 약 80~110원
      (quality "low"로 낮추면 약 20~30원. IMAGE_QUALITY 상수로 조절)
    - 매일 1회 × 30일 = 월 약 2,500~3,300원 (medium 기준)

종료 코드:
    0 = 성공 / 정상 skip
    1 = 입력 누락 (deep_dive·qt 파일, 참고 일러스트, OPENAI_API_KEY)
    2 = API 호출 실패
"""

import argparse
import base64
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
SCENES_DIR = PROJECT_ROOT / "src" / "images" / "scenes"
PROMPT_DIR = PROJECT_ROOT / "prompts" / "scene_image"
STYLE_PATH = PROMPT_DIR / "style.md"
BRIEF_SYSTEM_PATH = PROMPT_DIR / "brief_system.md"

# 항상 첨부하는 참고 일러스트 (화풍 기준) — 회원님이 지정한 경로
REFERENCE_IMAGE_PATH = PROJECT_ROOT / "src" / "images" / "참고 일러스트.png"

# 텍스트 모델 (브리프 생성)
BRIEF_MODEL = "gpt-4o-mini"
BRIEF_TEMPERATURE = 0.7
BRIEF_MAX_TOKENS = 600

# 이미지 모델 (2026-06 기준 최신은 gpt-image-2. 구버전 gpt-image-1은 "옛날 GPT" 느낌)
IMAGE_MODEL = "gpt-image-2"
IMAGE_SIZE = "1536x1024"   # 가로형 장면. 정사각=1024x1024, 세로형=1024x1536
IMAGE_QUALITY = "medium"   # "low" | "medium" | "high" — 비용·품질 trade-off

# 텍스트 가격 (백만 토큰당 USD) — gpt-4o-mini
PRICE_INPUT_PER_1M = 0.15
PRICE_OUTPUT_PER_1M = 0.60
USD_TO_KRW = 1500


# ===== 로깅 =====
def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now(KST).strftime("%H:%M:%S")
    prefix = {"INFO": "ℹ️ ", "OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "SKIP": "⏭️ "}.get(level, "• ")
    print(f"[{now}] {prefix} {msg}")


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


# ===== 입력 로드 =====
def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"JSON 로드 실패 ({path}): {e}", "WARN")
        return None


def build_source_context(date_str: str) -> dict | None:
    """deep_dive(필수) + qt(선택)에서 ①본문구절 ②주제 ③본문따라가기 추출."""
    deep_dive = load_json(DEEP_DIVE_DIR / f"{date_str}.json")
    if not deep_dive:
        log(f"deep_dive 데이터가 없습니다: data/deep_dive/{date_str}.json", "ERR")
        log("먼저 generate_meditation.py를 실행해주세요.", "ERR")
        return None

    qt = load_json(QT_DIR / f"{date_str}.json") or {}
    verses = qt.get("verses", [])
    body_text = "\n".join(f"{v['number']} {v['text']}" for v in verses) if verses else ""

    return {
        "본문_구절": body_text or deep_dive.get("scripture_ref", ""),
        "본문_참조": deep_dive.get("scripture_ref", ""),
        "주제": deep_dive.get("title", ""),
        "본문_따라가기": {
            "장면": deep_dive.get("장면", ""),
            "질문": deep_dive.get("질문", ""),
            "맥락": deep_dive.get("맥락", ""),
            "통찰": deep_dive.get("통찰", ""),
            "연결": deep_dive.get("연결", ""),
        },
    }


# ===== OpenAI 클라이언트 =====
def make_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 라이브러리가 없습니다. pip install openai python-dotenv")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다. .env 파일에 추가해주세요.")
    return OpenAI(api_key=api_key)


# ===== 1) 현재 상황 브리프 생성 (회원님이 손으로 쓰던 ④번) =====
def generate_brief(client, context: dict) -> dict:
    system_prompt = BRIEF_SYSTEM_PATH.read_text(encoding="utf-8")
    payload = {
        "본문_구절": context["본문_구절"],
        "주제": context["주제"],
        "본문_따라가기": context["본문_따라가기"],
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    resp = client.chat.completions.create(
        model=BRIEF_MODEL,
        messages=messages,
        temperature=BRIEF_TEMPERATURE,
        max_tokens=BRIEF_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    brief = json.loads(resp.choices[0].message.content)
    usage = resp.usage
    cost_usd = (usage.prompt_tokens / 1_000_000 * PRICE_INPUT_PER_1M
                + usage.completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M)
    log(f"브리프 생성 OK · 약 {cost_usd * USD_TO_KRW:.2f}원", "OK")
    return brief


# ===== 2) 최종 이미지 프롬프트 조립 =====
def build_image_prompt(context: dict, brief: dict) -> str:
    style = STYLE_PATH.read_text(encoding="utf-8").strip()
    # style.md는 머리말 설명(맨 위 주석)이 포함돼 있으니 본문만 사용하도록 구분선 이후를 취함
    if "---" in style:
        style = style.split("---", 1)[1].strip()

    배경 = brief.get("배경", "")

    # ③ 본문 따라가기(5단 호흡) — 회원님 원래 공식대로 이미지 프롬프트에 직접 첨부
    dd = context.get("본문_따라가기", {})
    따라가기_lines = []
    for key in ["장면", "질문", "맥락", "통찰", "연결"]:
        val = (dd.get(key) or "").strip()
        if val:
            따라가기_lines.append(f"· {key}: {val}")
    따라가기 = "\n".join(따라가기_lines)

    return (
        f"{style}\n\n"
        f"[오늘 그릴 장면]\n"
        f"① 성경 본문: {context['본문_참조']}\n"
        f"② 주제: {context['주제']}\n\n"
        f"③ 본문 따라가기 (오늘 묵상의 흐름 — 장면을 이해하는 맥락으로 참고):\n{따라가기}\n\n"
        f"④ 현재 상황\n"
        f"■ 배경 (디테일·채도 낮게, 상징 표식만):\n{배경}"
    )


# ===== 3) 이미지 생성 =====
def generate_image(client, prompt: str, out_path: Path, quality: str = IMAGE_QUALITY,
                   model: str = IMAGE_MODEL) -> None:
    if not REFERENCE_IMAGE_PATH.exists():
        raise RuntimeError(f"참고 일러스트가 없습니다: {REFERENCE_IMAGE_PATH}")

    # 참고 일러스트를 항상 첨부 → images.edit으로 화풍 고정
    with open(REFERENCE_IMAGE_PATH, "rb") as ref:
        resp = client.images.edit(
            model=model,
            image=[ref],
            prompt=prompt,
            size=IMAGE_SIZE,
            quality=quality,
        )

    # 실측 비용 로깅 (gpt-image-2: 텍스트입력 $5 / 이미지입력 $8 / 이미지출력 $30 per 1M tokens)
    try:
        u = resp.usage
        det = getattr(u, "input_tokens_details", None)
        text_in = getattr(det, "text_tokens", 0) or 0
        img_in = getattr(det, "image_tokens", 0) or 0
        out_tok = getattr(u, "output_tokens", 0) or 0
        cost_usd = text_in / 1e6 * 5 + img_in / 1e6 * 8 + out_tok / 1e6 * 30
        log(f"이미지 비용 실측: ${cost_usd:.4f} (약 {cost_usd * USD_TO_KRW:.1f}원) "
            f"[텍스트입력 {text_in} · 이미지입력 {img_in} · 출력 {out_tok} 토큰]", "OK")
    except Exception:
        pass  # usage 구조가 다르면 비용 로깅만 건너뜀 (생성은 정상)

    b64 = resp.data[0].b64_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(b64))
    log(f"이미지 저장 완료: {out_path}", "OK")


# ===== 메인 =====
def main() -> int:
    parser = argparse.ArgumentParser(description="오늘의 장면 일러스트 생성기")
    parser.add_argument("date_pos", nargs="?", default=None, help="날짜 YYYY-MM-DD (생략 시 오늘)")
    parser.add_argument("--date", default=None, help="날짜 (positional 대신)")
    parser.add_argument("--force", action="store_true", help="이미 있어도 재생성")
    parser.add_argument("--dry-run", action="store_true", help="이미지 생성 없이 프롬프트만 출력(무료)")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default=IMAGE_QUALITY,
                        help=f"이미지 품질 (기본 {IMAGE_QUALITY}). high일수록 질감이 살지만 비쌈.")
    parser.add_argument("--model", default=IMAGE_MODEL,
                        help=f"이미지 모델 (기본 {IMAGE_MODEL}). 예: gpt-image-2, chatgpt-image-latest, gpt-image-1")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        log("python-dotenv 미설치 — 환경변수를 직접 사용합니다.", "WARN")

    date_str = args.date_pos or args.date or today_str()

    log("=" * 50)
    log(f"장면 일러스트 생성 시작 (날짜: {date_str})")
    log("=" * 50)

    out_path = SCENES_DIR / f"{date_str}.png"
    if out_path.exists() and not args.force and not args.dry_run:
        log(f"이미지가 이미 있습니다 → 건너뜁니다: {out_path.name}", "SKIP")
        log("재생성하려면 --force 를 사용해주세요.")
        return 0

    # 입력 검증
    for p, name in [(STYLE_PATH, "style.md"), (BRIEF_SYSTEM_PATH, "brief_system.md")]:
        if not p.exists():
            log(f"프롬프트 파일이 없습니다: {name} ({p})", "ERR")
            return 1
    if not REFERENCE_IMAGE_PATH.exists():
        log(f"참고 일러스트가 없습니다: {REFERENCE_IMAGE_PATH}", "ERR")
        return 1

    context = build_source_context(date_str)
    if not context:
        return 1
    log(f"본문: {context['주제']} ({context['본문_참조']})", "OK")

    # dry-run: API 호출 없이 프롬프트만 — 단, 브리프는 GPT가 만들어야 하므로
    # dry-run에서도 브리프는 생성(소액)하되, 이미지 호출만 생략
    try:
        client = make_client()
    except RuntimeError as e:
        log(str(e), "ERR")
        return 1

    try:
        brief = generate_brief(client, context)
    except Exception as e:
        log(f"브리프 생성 실패: {e}", "ERR")
        return 2

    prompt = build_image_prompt(context, brief)

    if args.dry_run:
        log("[DRY RUN] 이미지 생성 생략 — 최종 프롬프트만 출력합니다.")
        print("\n" + "─" * 50)
        print(prompt)
        print("─" * 50)
        return 0

    try:
        log(f"이미지 생성 중 (model={args.model}, quality={args.quality})...", "INFO")
        generate_image(client, prompt, out_path, quality=args.quality, model=args.model)
    except Exception as e:
        log(f"이미지 생성 실패: {e}", "ERR")
        return 2

    log("=" * 50)
    log(f"완료 — step-2 페이지에서 '🎬 오늘의 장면 그림 보기'로 확인하세요.", "OK")
    log("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
