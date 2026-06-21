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


def build_source_context(date_str: str, variant_index: int | None = None) -> dict | None:
    """deep_dive(필수) + qt(선택)에서 ①본문구절 ②주제 ③본문따라가기 추출.

    variant_index가 주어지고 deep_dive에 variants 배열이 있으면, 해당 변형의
    5단 호흡으로 본문_따라가기를 구성한다(변형마다 다른 그림이 나오도록).
    out_name(저장 파일명)도 함께 반환한다.
    """
    deep_dive = load_json(DEEP_DIVE_DIR / f"{date_str}.json")
    if not deep_dive:
        log(f"deep_dive 데이터가 없습니다: data/deep_dive/{date_str}.json", "ERR")
        log("먼저 generate_meditation.py를 실행해주세요.", "ERR")
        return None

    qt = load_json(QT_DIR / f"{date_str}.json") or {}
    verses = qt.get("verses", [])
    body_text = "\n".join(f"{v['number']} {v['text']}" for v in verses) if verses else ""

    # 변형 선택: variants 배열이 있고 인덱스가 유효하면 그 변형의 5키를 사용
    variants = deep_dive.get("variants")
    if variant_index is not None and isinstance(variants, list) and variant_index < len(variants):
        src = variants[variant_index]
        out_name = src.get("scene_image") or (f"{date_str}.png" if variant_index == 0 else f"{date_str}-{variant_index + 1}.png")
        # 본문 순서 분할 변형이면, 그림도 해당 구간 절만 보도록 본문을 좁혀 더 다른 장면이 나오게 함
        seg = src.get("구간")
        if seg and verses and "-" in str(seg):
            try:
                a, b = (int(x) for x in str(seg).split("-", 1))
                seg_verses = [v for v in verses if a <= v.get("number", -1) <= b]
                if seg_verses:
                    body_text = "\n".join(f"{v['number']} {v['text']}" for v in seg_verses)
            except ValueError:
                pass
    else:
        src = deep_dive
        out_name = f"{date_str}.png"

    return {
        "본문_구절": body_text or deep_dive.get("scripture_ref", ""),
        "본문_참조": deep_dive.get("scripture_ref", ""),
        "주제": deep_dive.get("title", ""),
        "본문_따라가기": {
            "장면": src.get("장면", ""),
            "질문": src.get("질문", ""),
            "맥락": src.get("맥락", ""),
            "통찰": src.get("통찰", ""),
            "연결": src.get("연결", ""),
        },
        "out_name": out_name,
        "variant_count": len(variants) if isinstance(variants, list) else 1,
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


# ===== 캐릭터 외형 사전 (인물 일관성) =====
# 인물별 외형(신체비율·헤어·얼굴·의상)을 영구 저장해, 같은 인물은 매일·매 장면 똑같이 그리도록 함.
CHAR_REGISTRY_PATH = PROJECT_ROOT / "data" / "character_appearance.json"
CHAR_VISION_MODEL = "gpt-4o-mini"  # 멀티모달 — 그림에서 외형을 읽어옴
CHAR_FIELDS = ["신체비율", "헤어스타일", "얼굴", "의상"]


def load_char_registry() -> dict:
    return load_json(CHAR_REGISTRY_PATH) or {}


def save_char_registry(reg: dict) -> None:
    CHAR_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHAR_REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def day_character_names(date_str: str) -> list[str]:
    """ai/{date}.json의 등장인물 이름 목록."""
    ai = load_json(PROJECT_ROOT / "data" / "ai" / f"{date_str}.json") or {}
    names = []
    for c in ai.get("characters", []) or []:
        n = (c.get("name") or "").strip()
        if n:
            names.append(n)
    return names


def appearance_line(entry: dict) -> str:
    """레지스트리 엔트리를 한 줄 묘사로 합침."""
    parts = [f"{f} {entry[f]}" for f in CHAR_FIELDS if entry.get(f)]
    return "; ".join(parts) if parts else (entry.get("외형", "") or "")


def describe_characters_from_image(client, image_path: Path, names: list[str], hint: str = "") -> dict:
    """그림에서 지정 인물들의 외형(신체비율·헤어·얼굴·의상)을 읽어와 dict로 반환.

    hint: 인물의 '역할/행동' 설명. 그림 속 누가 누구인지 정확히 식별하도록 돕는다.
    """
    if not image_path.exists() or not names:
        return {}
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    system = (
        "너는 동화책 일러스트의 캐릭터 디자이너야. 주어진 그림에서 지정한 인물들의 '외형'만 묘사해. "
        "먼저 아래 '인물 역할/장면' 설명을 보고 그림 속 누가 누구인지 정확히 식별한 뒤, "
        "각 인물마다 신체비율(체격·키 인상), 헤어스타일(색·길이·모양), 얼굴(나이대·수염·인상), "
        "의상(색·형태·소품)을 간결한 한국어 명사구로 적어. 그림에 분명히 보이지 않는 인물은 결과에서 빼(상상 금지). "
        '오직 JSON만 출력: {"characters":[{"name":"","신체비율":"","헤어스타일":"","얼굴":"","의상":""}]}'
    )
    user_text = "묘사할 인물: " + ", ".join(names)
    if hint:
        user_text += "\n\n[인물 역할/장면 — 식별 참고]\n" + hint
    user_content = [
        {"type": "text", "text": user_text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    resp = client.chat.completions.create(
        model=CHAR_VISION_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=0.2,
        max_tokens=700,
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {}
    out = {}
    for c in parsed.get("characters", []):
        n = (c.get("name") or "").strip()
        if n:
            out[n] = {f: (c.get(f) or "").strip() for f in CHAR_FIELDS}
    u = resp.usage
    cost = (u.prompt_tokens / 1e6 * PRICE_INPUT_PER_1M + u.completion_tokens / 1e6 * PRICE_OUTPUT_PER_1M)
    log(f"캐릭터 외형 분석 OK ({len(out)}명) · 약 {cost * USD_TO_KRW:.2f}원", "OK")
    return out


def build_identify_hint(date_str: str, scene_text: str = "") -> str:
    """vision 식별용 힌트: 인물 역할(ai characters) + 그 그림의 장면 설명."""
    ai = load_json(PROJECT_ROOT / "data" / "ai" / f"{date_str}.json") or {}
    lines = []
    if scene_text:
        lines.append(f"장면: {scene_text.strip()}")
    for c in ai.get("characters", []) or []:
        n = (c.get("name") or "").strip()
        d = (c.get("description") or "").strip()
        if n and d:
            lines.append(f"- {n}: {d}")
    return "\n".join(lines)


def seed_appearances(client, date_str: str, image_path: Path, names: list[str], overwrite: bool,
                     scene_text: str = "") -> dict:
    """image_path에서 인물 외형을 읽어 레지스트리에 반영. overwrite=False면 신규(미등록)만 추가."""
    reg = load_char_registry()
    targets = names if overwrite else [n for n in names if n not in reg]
    if not targets:
        return reg
    hint = build_identify_hint(date_str, scene_text)
    described = describe_characters_from_image(client, image_path, targets, hint=hint)
    now = datetime.now(KST).isoformat()
    for n, attrs in described.items():
        if not overwrite and n in reg:
            continue
        entry = reg.get(n, {})
        entry.update(attrs)
        entry["ref_image"] = f"scenes/{image_path.name}"
        entry.setdefault("first_seen", date_str)
        entry["updated_at"] = now
        reg[n] = entry
        log(f"  · 외형 저장: {n} — {appearance_line(entry)[:50]}…", "OK")
    save_char_registry(reg)
    return reg


def appearances_for_scene(context: dict, names: list[str]) -> list[tuple[str, str]]:
    """레지스트리에서, 이 장면에 실제로 등장할 법한 인물의 외형 줄을 추린다.
    (브리프 인물/5단 호흡 장면 텍스트에 이름이 나오는 인물만)."""
    reg = load_char_registry()
    scene_text = (context.get("본문_따라가기", {}) or {}).get("장면", "") or ""
    brief_people = context.get("_brief_people", "") or ""
    # 실제 '그려질' 인물은 브리프의 인물 설명이 가장 정확(서사 텍스트엔 죽은 인물도 언급됨).
    # 브리프 인물이 있으면 그걸 우선 기준으로, 비어 있으면 장면 텍스트로 폴백.
    haystack = brief_people if brief_people.strip() else scene_text
    picked = []
    for n in names:
        if n in reg and n in haystack:
            picked.append((n, appearance_line(reg[n])))
    return picked


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
def build_image_prompt(context: dict, brief: dict, appearances: list | None = None) -> str:
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

    # ★ 캐릭터 일관성 — 등장인물 고정 외형을 항상 동일하게 그리도록 명시
    consistency_block = ""
    if appearances:
        lines = "\n".join(f"· {name}: {desc}" for name, desc in appearances if desc)
        if lines:
            consistency_block = (
                "[캐릭터 일관성 — 매우 중요]\n"
                "아래 인물은 매일·매 장면에서 반드시 동일한 외형(신체비율·헤어·얼굴·의상)으로 그리세요. "
                "장면이 달라도 같은 사람으로 알아볼 수 있어야 합니다.\n"
                f"{lines}\n\n"
            )

    return (
        f"{style}\n\n"
        f"{consistency_block}"
        f"[오늘 그릴 장면]\n"
        f"① 성경 본문: {context['본문_참조']}\n"
        f"② 주제: {context['주제']}\n\n"
        f"③ 본문 따라가기 (오늘 묵상의 흐름 — 장면을 이해하는 맥락으로 참고):\n{따라가기}\n\n"
        f"④ 현재 상황\n"
        f"■ 배경 (디테일·채도 낮게, 상징 표식만):\n{배경}"
    )


# ===== 3) 이미지 생성 =====
def generate_image(client, prompt: str, out_path: Path, quality: str = IMAGE_QUALITY,
                   model: str = IMAGE_MODEL, extra_refs: list | None = None) -> None:
    if not REFERENCE_IMAGE_PATH.exists():
        raise RuntimeError(f"참고 일러스트가 없습니다: {REFERENCE_IMAGE_PATH}")

    # 참고 일러스트(화풍 기준)는 항상 첨부. extra_refs(예: 같은 날 1번 이미지)를 더 붙여 인물 외형을 추가로 고정.
    open_files = [open(REFERENCE_IMAGE_PATH, "rb")]
    try:
        for rp in (extra_refs or []):
            if rp and Path(rp).exists():
                open_files.append(open(rp, "rb"))
        resp = client.images.edit(
            model=model,
            image=open_files,
            prompt=prompt,
            size=IMAGE_SIZE,
            quality=quality,
        )
    finally:
        for f in open_files:
            f.close()

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
    parser.add_argument("--all-variants", action="store_true",
                        help="deep_dive의 variants 배열만큼 변형별 장면을 모두 생성 ({date}.png, {date}-2.png …)")
    parser.add_argument("--variant", type=int, default=None,
                        help="특정 변형 1개만 생성 (1-based). 예: --variant 2 → {date}-2.png")
    parser.add_argument("--anchor", default=None,
                        help="기준 이미지 경로. 이 그림에서 인물 외형(텍스트)을 읽어 사전에 저장(덮어쓰기)함. 이미지 자체를 참고로 붙이진 않음.")
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

    # 입력 검증
    for p, name in [(STYLE_PATH, "style.md"), (BRIEF_SYSTEM_PATH, "brief_system.md")]:
        if not p.exists():
            log(f"프롬프트 파일이 없습니다: {name} ({p})", "ERR")
            return 1
    if not REFERENCE_IMAGE_PATH.exists():
        log(f"참고 일러스트가 없습니다: {REFERENCE_IMAGE_PATH}", "ERR")
        return 1

    # 생성할 변형 인덱스 목록 결정
    if args.all_variants:
        probe = build_source_context(date_str, variant_index=0)
        if not probe:
            return 1
        variant_indices = list(range(max(1, probe.get("variant_count", 1))))
        log(f"--all-variants: 변형 {len(variant_indices)}개 생성 예정", "INFO")
    elif args.variant is not None:
        variant_indices = [args.variant - 1]   # 1-based → 0-based
    else:
        variant_indices = [None]

    try:
        client = make_client()
    except RuntimeError as e:
        log(str(e), "ERR")
        return 1

    # 캐릭터 외형 사전 — 오늘 등장인물
    char_names = day_character_names(date_str)

    # --anchor: 기준 이미지에서 인물 외형을 읽어 사전에 저장(덮어쓰기) + 참고 이미지로 사용
    anchor_path = None
    if args.anchor:
        anchor_path = Path(args.anchor)
        if not anchor_path.is_absolute():
            anchor_path = PROJECT_ROOT / args.anchor
        if not anchor_path.exists():
            log(f"--anchor 이미지가 없습니다: {anchor_path}", "ERR")
            return 1
        if not args.dry_run:
            log(f"기준 이미지에서 인물 외형 추출 중: {anchor_path.name}", "INFO")
            # 기준 이미지에 해당하는 변형의 장면 설명을 식별 힌트로 사용
            _dd = load_json(DEEP_DIVE_DIR / f"{date_str}.json") or {}
            _scene = ""
            for _v in (_dd.get("variants") or []):
                if _v.get("scene_image") == anchor_path.name:
                    _scene = _v.get("장면", "")
                    break
            if not _scene:
                _scene = _dd.get("장면", "")
            seed_appearances(client, date_str, anchor_path, char_names, overwrite=True, scene_text=_scene)

    for vi in variant_indices:
        context = build_source_context(date_str, variant_index=vi)
        if not context:
            return 1
        out_path = SCENES_DIR / context["out_name"]
        label = f"변형 {vi + 1}" if vi is not None else "단일"
        log(f"[{label}] 본문: {context['주제']} ({context['본문_참조']}) → {out_path.name}", "OK")

        if out_path.exists() and not args.force and not args.dry_run:
            log(f"[{label}] 이미지가 이미 있습니다 → 건너뜁니다: {out_path.name} (재생성: --force)", "SKIP")
            continue

        try:
            brief = generate_brief(client, context)
        except Exception as e:
            log(f"[{label}] 브리프 생성 실패: {e}", "ERR")
            return 2

        # 이 장면에 등장하는 인물의 고정 외형을 사전에서 가져와 프롬프트에 주입
        context["_brief_people"] = brief.get("인물", "") if isinstance(brief, dict) else ""
        appearances = appearances_for_scene(context, char_names)
        if appearances:
            log(f"[{label}] 캐릭터 일관성 적용: {', '.join(n for n, _ in appearances)}", "INFO")
        prompt = build_image_prompt(context, brief, appearances)

        # 인물 일관성은 '텍스트 설명'으로만 맞춤 — 이전 이미지를 참고로 붙이면 표정·각도까지 복제돼
        # 어색해지므로 시각 참고는 화풍 기준(참고 일러스트)만 사용한다.
        extra_refs = []

        if args.dry_run:
            log(f"[{label}] [DRY RUN] 이미지 생성 생략 — 최종 프롬프트만 출력합니다.")
            print("\n" + "─" * 50)
            print(prompt)
            print("─" * 50)
            continue

        try:
            log(f"[{label}] 이미지 생성 중 (model={args.model}, quality={args.quality})...", "INFO")
            generate_image(client, prompt, out_path, quality=args.quality, model=args.model,
                           extra_refs=extra_refs)
        except Exception as e:
            log(f"[{label}] 이미지 생성 실패: {e}", "ERR")
            return 2

        # 첫 변형을 그린 직후: 그 그림에서 인물 외형(텍스트)을 사전에 보충(신규만) → 이후 변형/다음 날에 재사용
        if vi == 0 and not anchor_path:
            seed_appearances(client, date_str, out_path, char_names, overwrite=False,
                             scene_text=context.get("본문_따라가기", {}).get("장면", ""))

    log("=" * 50)
    log(f"완료 — step-2 페이지에서 '오늘의 장면'으로 확인하세요.", "OK")
    log("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
