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
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import bible_chapter
import biblehub_lookup
import openbible_xref

# ===== 설정 =====
KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).parent.parent
QT_DIR = PROJECT_ROOT / "data" / "qt"
REF_DIR = PROJECT_ROOT / "data" / "reference"

MODEL = "gpt-4o"          # 기존 파이프라인과 동일 모델
TEMPERATURE = 0.1         # 사실 조사이므로 낮게 — 회차 일관성↑ (2026-07-15: 0.3→0.1, seed와 병행)
SEED = 7                  # 같은 장 재생성 시 결과 재현성 확보(OpenAI best-effort). 고정값.
MAX_TOKENS = 10000        # 장 전체 + 인물 배경 + 4~6문장 신학핵심으로 KB가 두꺼워져 8000→10000

# "문화관습" 태그가 이 출처들뿐이면 실제 반증 근거(교차 사례·역사기록) 없이 붙은 것으로
# 보고 코드가 자동으로 "본문관찰"로 강등한다. generate_chapter_kb() 참고.
WEAK_SOURCES = {"개역개정 본문 관찰", "일반 지식(미확정)"}

# 우리가 프롬프트에 실제로 먹인 주석이 아닌데 모델이 '기억'으로 붙였을 수 있는 대표 공개주석가들.
# source에 이 이름이 있는데 이번 회차에 먹인 근거(꼬리표)가 아니면 "일반 지식(미확정)"으로 강등한다.
KNOWN_COMMENTATORS = {
    "gill", "barnes", "keil", "delitzsch", "jamieson", "fausset", "brown",
    "ellicott", "matthew henry", "henry", "clarke", "poole", "benson",
    "calvin", "exell", "pulpit", "cambridge", "expositor", "meyer",
}


def _build_fed_index(vc: dict, book_name: str, chapter) -> tuple[set, dict]:
    """이번 회차에 실제로 프롬프트에 먹인 주석의 (저자, 참조) 목록 — 앵커 확정의 '정답지'.

    vc = {절번호: [(저자, 본문), ...]}.
    반환: (fed_pairs={(저자소문자, "책 장:절")}, fed_authors={저자소문자: (표기용_이름, {참조들})})
    """
    fed_pairs: set = set()
    fed_authors: dict = {}
    for v, clist in (vc or {}).items():
        ref = f"{book_name} {chapter}:{v}"
        for author, _ in clist or []:
            al = author.strip().lower()
            fed_pairs.add((al, ref))
            disp, refs = fed_authors.get(al, (author.strip(), set()))
            refs.add(ref)
            fed_authors[al] = (disp, refs)
    return fed_pairs, fed_authors


def _normalize_source(source: str, fed_pairs: set, fed_authors: dict) -> str:
    """모델이 적은 source를, '우리가 실제로 먹인 주석'에만 근거해 확정하거나 강등한다.

    - 먹인 주석 꼬리표 [저자 · 책 장:절] → "저자, 책 장:절"로 확정(추적 가능·지어내기 0).
    - 우리가 준 적 없는 꼬리표/주석가 이름(모델 기억) → "일반 지식(미확정)"으로 강등.
    - 본문관찰·Strong's 등 비주석 근거는 그대로 둔다.
    """
    if not source:
        return source
    s = source.strip()

    # 1) 꼬리표 형태 [저자 · 책 장:절]
    m = re.search(r"\[([^\]·]+?)·([^\]]+?)\]", s)
    if m:
        author, ref = m.group(1).strip(), m.group(2).strip()
        if (author.lower(), ref) in fed_pairs:
            return f"{author}, {ref}"
        return "일반 지식(미확정)"        # 준 적 없는 꼬리표 = 지어냄

    # 2) 꼬리표 없이 주석가 이름만 등장
    low = s.lower()
    hit = next((al for al in fed_authors if al and al in low), None)
    if hit:
        disp, refs = fed_authors[hit]
        # 그 저자를 한 절에만 먹였고 source에 절 표기가 없으면 앵커를 부착해 확정
        if len(refs) == 1 and not re.search(r"\d+\s*:\s*\d+", s):
            return f"{disp}, {next(iter(refs))}"
        return source                     # 저자는 실제로 먹였음 — 그대로 둔다
    if any(c in low for c in KNOWN_COMMENTATORS):
        return "일반 지식(미확정)"        # 안 먹인 주석가 이름 = 모델 기억
    return source

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


def passage_verses_in(qt_data: dict, chapter: str) -> set[int]:
    """그날 본문 중 이 장에 속하는 절 번호들. 장 넘김 본문(예: 6:19-7:2)도 처리."""
    return {
        int(v["number"])
        for v in qt_data.get("verses", [])
        if str(v.get("chapter", chapter)) == str(chapter) and str(v.get("number", "")).isdigit()
    }


def covered_verses(chapter_dict: dict) -> set[int]:
    """이 장 KB의 key_details가 실제로 다루는 절 번호들.

    verse 필드는 "6:3" · "6:5-7" · "3" 같은 형태로 들어온다.
    """
    covered: set[int] = set()
    for kd in (chapter_dict or {}).get("key_details", []) or []:
        ref = str(kd.get("verse", ""))
        tail = ref.split(":")[-1]           # "6:5-7" → "5-7"
        for part in tail.split(","):
            m = re.match(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*$", part)
            if not m:
                continue
            start = int(m.group(1))
            end = int(m.group(2) or start)
            covered.update(range(start, end + 1))
    return covered


def needs_regen(chapter_dict: dict, qt_data: dict, chapter: str) -> bool:
    """오늘 본문 구간에 KB 항목이 하나도 없으면 이 장은 다시 조사해야 한다.

    예전에는 '장이 KB에 있으면 무조건 skip'이었다. 그런데 KB는 그날 본문 절만 보고
    만들어졌으므로, 한 장이 여러 날에 걸치면 뒷날 구간은 KB가 텅 빈 채로 skip됐다.
    (2026-07-14 사무엘하 6:12-23 = 지식 0개로 묵상 생성)
    """
    todays = passage_verses_in(qt_data, chapter)
    if not todays:
        return False
    return not (todays & covered_verses(chapter_dict))


def _verse_nums(ref) -> set:
    """'7:12' · '7:5-7' · '5,7' · '12' → {정수 절번호들}."""
    out = set()
    tail = str(ref).split(":")[-1]
    for part in tail.split(","):
        m = re.match(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*$", part)
        if m:
            a = int(m.group(1)); b = int(m.group(2) or a)
            out.update(range(a, b + 1))
    return out


def merge_chapter_kb(existing, new: dict, passage_nums) -> dict:
    """오늘 구간 KB(new)를 기존 장 KB(existing)에 이어붙인다(구간별 누적, 재실행 멱등).

    - key_details: 오늘 구간에 속한 기존 항목만 새것으로 교체, 다른 구간은 그대로 보존.
    - 인물: 이름 기준 합집합.  주의점: 텍스트 기준 합집합.
    - 신학_핵심: 새 내용이 기존에 이미 없으면 이어붙임(날짜별 누적).
    """
    if not existing or not isinstance(existing, dict):
        return new
    pset = {int(v) for v in passage_nums} if passage_nums else set()
    merged = dict(existing)

    kept = [kd for kd in existing.get("key_details", [])
            if not (pset and (_verse_nums(kd.get("verse", "")) & pset))]
    merged["key_details"] = kept + list(new.get("key_details", []))

    seen = {p.get("인물") for p in existing.get("인물", [])}
    merged["인물"] = list(existing.get("인물", [])) + [
        p for p in new.get("인물", []) if p.get("인물") not in seen]

    ex_notes = list(existing.get("주의점", []))
    merged["주의점"] = ex_notes + [n for n in new.get("주의점", []) if n not in ex_notes]

    ex_th = (existing.get("신학_핵심") or "").strip()
    nw_th = (new.get("신학_핵심") or "").strip()
    if not ex_th:
        merged["신학_핵심"] = nw_th
    elif nw_th and nw_th not in ex_th:
        merged["신학_핵심"] = ex_th + " " + nw_th
    else:
        merged["신학_핵심"] = ex_th
    return merged


# ===== 프롬프트 =====
SYSTEM_PROMPT = """당신은 개혁주의·복음주의 전통에 충실한 성경 주석 조사원입니다.
주어진 성경 '한 장'에 대해, 큐티 묵상 집필에 쓸 **검증 가능한 사실 지식(KB)**을 JSON으로 정리합니다.

[수집·서술 원칙 — 반드시 지킬 것]
1. 본문 관찰이 먼저입니다. 본문이 실제로 말하는 것에서 출발하세요.
2. **추측 금지.** 확실하지 않으면 넣지 말거나 confidence를 낮추고, 불확실함을 명시하세요.
   특히 히브리어 어원·지명 위치·숫자는 표준적으로 확실한 것만 적습니다. 어원을 지어내지 마세요.
3. 정통 안에서도 견해가 갈리는 지점(인물/사물의 정체, 번역 차이, 사건 해석)은
   반드시 '주의점'에 "견해가 갈린다"고 명시하고, 한쪽으로 단정하지 마세요.
4. source에는 근거를 **구체적으로** 적으세요.
   - 공개 주석을 근거로 삼았으면, 그 주석 앞에 붙은 **대괄호 꼬리표(예: [Gill · 사무엘하 7:16])를 통째로** source에 옮겨 적으세요. 꼬리표에 없는 주석가 이름을 당신의 기억으로 새로 지어내지 마세요(예: 제공되지 않은 "Barnes"를 임의로 붙이지 말 것 — 제공된 꼬리표만 씁니다).
   - 어원은 "Strong's H####"로, 자료 없이 본문 자체 관찰이면 "개역개정 본문 관찰"로 적습니다.
   - 근거가 불확실하면 "일반 지식(미확정)"이라고 정직히 적고, "공개 주석"처럼 뭉뚱그리지 마세요.
5. 과도한 도덕적 정죄나 인물 미화를 피하고, 본문이 말하는 범위를 넘지 마세요.
6. **"문화관습"으로 태그를 붙이려면 그 장 안에서 딱 한 번 있었던 개인의 행동만으로 "당시 ~문화·관습을 보여준다"고 일반화하지 마세요.**
   진짜 문화관습이면 반증할 근거(다른 성경 구절의 같은 관습, 역사적 기록, 정통 주석의 언급)를 source에 구체적으로 적으세요
   (예: "낮잠 관습 — 창 18:1 '날이 뜨거울 때' 참조" 처럼). 그런 근거를 못 대겠으면 문화관습이 아니라 "본문관찰"로 적으세요
   — source가 "개역개정 본문 관찰"이나 "일반 지식(미확정)"뿐이면 그건 아직 문화관습이라고 부를 근거가 부족하다는 뜻입니다.

[출력 형식 — 오직 JSON 객체 하나. 설명 문장 금지]
{
  "key_details": [
    {"verse": "장:절 또는 장:절-절", "cat": "지리|어원|문화관습|신학핵심|본문관찰|인물배경",
     "fact": "한 문장으로 명료하게", "source": "근거", "confidence": "high|medium|low"}
  ],
  "인물": [
    {"인물": "이름", "배경": "이 인물이 누구인가 — 정체·다른 본문에서의 등장·이후 역할(확실한 것만)",
     "상황": "이 장에서의 처지·행동", "감정": "내면·긴장"}
  ],
  "신학_핵심": "이 장의 핵심 신학을 4~6문장으로 — 하나님의 성품·행하심, 언약/구속사적 위치, (본문·주석이 뒷받침하면) 신약에서의 성취까지",
  "주의점": ["오해·과장을 막을 경고 + 주석마다 견해가 갈리는 지점을 구체적으로 (2~4개)"]
}

[key_details 조사 방식 — 절별로 훑으세요. 장 전체에서 아무렇게나 6~9개만 골라 담지 마세요.]
받은 절을 처음부터 끝까지 하나씩 읽으며, 각 절마다 아래 5개 카테고리 관점에서 다룰 만한 게 있는지 점검하세요.
- 지리: 그 절에 지명·장소가 나오는가?
- 어원: 그 절에 원어 뜻을 밝히면 이해가 달라지는 단어·이름이 있는가? **인물 이름·지명 자체도 히브리어 단어이므로 반드시 포함합니다** — 새로 등장하는 인물·지명의 이름이 나오면, 그 이름 자체의 히브리어 어원·뜻을 확인하세요. (예: 사울 집안 인물 중 "-바알"이 후대에 "-보셋(수치)"으로 치환된 이름들이 있다는 게 널리 알려진 텍스트비평 논점입니다 — 이런 식으로 이름 하나에도 다룰 만한 원어 배경이 있는지 확인합니다.) 표준 주석·사전(Strong's, BDB, 개역개정 각주 등)에서 확인되는 것만 적고, 정확한 뜻풀이가 불확실하거나 주석마다 갈리면 confidence를 medium/low로 낮추고 그 불확실성을 fact에 명시하세요. 지어내지 마세요.
- 문화관습: 그 절에 당시 제도·의식·관습·사회 규범이 드러나는가?
- 본문관찰: 그 절에 무심코 지나치기 쉬운 디테일·반복·대조가 있는가?
- 인물배경: 그 절에 나오는 인물의 정체·과거·관계에 설명이 필요한가?

**어원 항목은 '뜻이 본문 이해나 묵상을 실제로 바꾸는' 이름·단어에 담으세요.** 처음 등장하는 이름이라고 기계적으로 어원 항목을 만들지는 마세요 — 뜻이 그날 묵상에 아무 차이를 주지 않으면 굳이 넣지 않습니다. (반대로 "베레스웃사=웃사의 파멸"처럼 사건·해석과 맞물린 이름 뜻은 담습니다.) 어원은 6개 카테고리 중 하나일 뿐이니, 아래 [배경] 항목보다 앞세우지 마세요.

**[배경] 낯선 물건·제도·행동, 그리고 본문이 이유를 대지 않는 인과는 반드시 담으세요.** 그 시대엔 당연했지만 오늘 독자에겐 낯선 것(예: 새 수레·에봇·번제·춤·옷 찢기)과, 본문이 "왜"를 말하지 않고 결과만 말하는 대목(예: 수레로 궤를 옮기자 진노가 임함 — 왜 잘못인지 본문은 침묵)은 묵상이 걸려 넘어지는 지점이므로, 그 배경을 밝혀 담으세요(주로 문화관습·본문관찰·신학핵심). 단 배경도 표준 주석에서 확인되는 것만 적고, 불확실하면 confidence를 낮추고 그 불확실성을 명시하세요 — 지어내지 마세요.

**입력에 "Bible Hub 인터리니어 실측 자료"가 포함돼 있으면 그걸 최우선 근거로 삼으세요.** 그건 당신의 기억이 아니라 실제로 조회해 온 히브리어 원문·Strong's 번호·사전 뜻풀이입니다. 어원 항목의 source에는 해당 Strong's 번호(예: "Strong's H1196")를 적으세요. 그 자료에 없는 이름·단어를 다룰 땐 표준적으로 확실한 것만 보태고, 불확실하면 confidence를 낮추세요 — 이 실측 자료가 없다고 해서 어원 조사를 포기하지 말고, 그럴 땐 평소처럼 신중하게(지어내지 않고) 접근하세요.

다룰 게 있으면 반드시 기록하세요. 억지로 개수를 채우진 말되, 어떤 절을 "단순 서술"이라며 건너뛰기 전에 위 [배경] 기준부터 대보세요 — 낯선 물건이나 설명 없는 인과가 있으면 그건 건너뛸 절이 아닙니다. 순전히 연결·반복 서술이라 배경이 필요 없는 절만 건너뜁니다. 절 수가 많은 장은 key_details도 그만큼 자연히 늘어나야 하니, 개수를 미리 정해두지 말고 실제로 다룰 게 있는 만큼 담으세요. 같은 절이라도 카테고리가 다르면 항목을 여러 개 만들 수 있습니다.

인물은 2~4명 — 주인공만이 아니라 그 장에서 말하거나 행동하는 조연(선지자·사자·왕족 등)도 포함하고, 각자의 '배경'(정체·다른 본문에서의 등장·이후 역할)을 확인해 담으세요(확실한 것만, 불확실하면 비우거나 완곡히).

전반적으로 — KB는 이 자료를 바탕으로 쓰일 묵상·질문·적용보다 **더 두껍고 근거가 분명해야** 합니다. 얕게 요약하지 말고, 손에 쥔 자료(장 전체 본문·어원·관주·주석)에서 확인되는 배경을 충분히 담되, 없는 것을 지어내지는 마세요. 한국어로 작성하세요."""


def build_user_prompt(
    qt_data: dict,
    chapter: str,
    biblehub_text: str | None = None,
    chapter_verses: list[dict] | None = None,
    xref_text: str | None = None,
    commentary_text: str | None = None,
    focus_label: str | None = None,
) -> str:
    book = qt_data.get("book_name", "")
    ref = qt_data.get("scripture_ref", "")

    payload = {"책": book, "장": chapter, "오늘_큐티_본문_참조": ref}

    if chapter_verses:
        # 장 전체는 '문맥 파악용'으로 쥐여 주되, 실제 KB는 오늘 구간에만 초점을 맞춘다.
        payload["장_전체_본문(문맥용)"] = "\n".join(
            f"{v['number']} {v['text']}" for v in chapter_verses
        )
        if focus_label:
            payload["오늘_다룰_구간"] = f"{book} {chapter}:{focus_label}"
            payload["지시"] = (
                f"위 '장_전체_본문(문맥용)'은 흐름 파악을 위한 {book} {chapter}장 전문입니다. "
                f"이번에 KB로 정리할 대상은 **오늘 구간({book} {chapter}:{focus_label})뿐**입니다. "
                "그 구간의 절을 처음부터 끝까지 **한 절씩 깊이** 훑어, 담을 만한 것을 빠짐없이 정리하세요 "
                "(짧은 구간이면 그만큼 각 절을 더 촘촘하게). "
                "이 구간 밖의 절은 이번에 만들지 마세요 — 다른 날 따로 다룹니다. "
                "장 전체 문맥은 참고하되 key_details·인물·신학_핵심·주의점은 모두 오늘 구간에 초점을 맞추세요."
            )
        else:
            payload["지시"] = (
                f"위 '장_전체_본문(문맥용)'은 개역개정 {book} {chapter}장 전문입니다. "
                "1절부터 끝까지 한 절도 빠짐없이 훑으며 각 절에 담을 만한 것을 정리하세요."
            )
    else:
        # 폴백: 장 전체 조회에 실패한 경우에만 예전 방식(그날 본문 절만)
        verses = qt_data.get("verses", [])
        payload["오늘_본문_절"] = "\n".join(
            f"{v.get('number','')} {v.get('text','')}" for v in verses
        )
        payload["지시"] = (
            f"위는 '{book} {chapter}장'에 속한 오늘 큐티 본문입니다. "
            f"'{book} {chapter}장' 전체를 대상으로, 이 본문 묵상에 도움이 될 KB를 위 형식으로 정리하세요. "
            "제공된 절 밖의 내용도 그 장에 속하면 당신의 지식으로 보완하되, 원칙(추측 금지·견해차 명시)을 지키세요."
        )

    if biblehub_text:
        payload["Bible_Hub_인터리니어_실측_자료"] = biblehub_text
    if xref_text:
        payload["관주_연결_자료"] = xref_text
    if commentary_text:
        payload["공개_주석_자료"] = commentary_text
    return json.dumps(payload, ensure_ascii=False)


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


def generate_chapter_kb(client, qt_data: dict, chapter: str, passage_nums=None) -> tuple[dict, dict]:
    """오늘 구간(passage_nums)의 KB를 생성해 (passage_dict, cost) 반환.

    passage_nums가 없으면 장 전체를 대상으로 폴백한다. 장 전체 본문은 문맥용으로 쓰고,
    관주·주석·프롬프트는 오늘 구간에 초점을 맞춘다(그날 본문에 집중해 더 깊게).
    """
    book = qt_data.get("book_name", "")
    # 장 전체 본문(개역개정) — 문맥 파악 + 폴백용.
    chapter_verses = bible_chapter.fetch_chapter(book, int(chapter), log=log)

    # 오늘 다룰 구간 절 번호. 없으면 장 전체.
    if passage_nums:
        focus_nums = sorted(int(v) for v in passage_nums)
    elif chapter_verses:
        focus_nums = [int(v["number"]) for v in chapter_verses]
    else:
        focus_nums = list(range(1, 30))
    focus_label = f"{focus_nums[0]}-{focus_nums[-1]}" if focus_nums else None

    # 관주(OpenBible cross-ref) — 오늘 구간 절에 초점. 실패 시 None(관주 없이 진행).
    xref_text = None
    try:
        xref_text = openbible_xref.build_chapter_xref_text(book, int(chapter), focus_nums)
        if xref_text:
            log(f"  OpenBible 관주: {xref_text.count(chr(10) + '- ')}개 절에 연결 구절 첨부", "INFO")
    except Exception as e:
        log(f"  OpenBible 관주 조회 실패(관주 없이 계속): {e}", "WARN")

    biblehub_text = None
    book_slug = biblehub_lookup.BOOK_SLUGS.get(qt_data.get("book_name", ""))
    if book_slug:
        try:
            research = biblehub_lookup.research_chapter(book_slug, int(chapter), max_strongs_lookups=25, log=log)
            if research.get("verses"):
                biblehub_text = biblehub_lookup.format_for_prompt(research)
        except Exception as e:
            log(f"  Bible Hub 조사 실패(기존 방식으로 계속 진행): {e}", "WARN")
    else:
        log(f"  Bible Hub 책 매핑 없음({qt_data.get('book_name','')}) — 원어 조사 없이 진행", "WARN")

    # 주석(Bible Hub 공개 PD 주석) — 배경 급소 절에만 선택적으로 붙인다(절당 33KB라 전량은 무겁다).
    # 급소 선정은 '연결 개수(breadth)' 기준 상위 5절 — 단일 최고 득표 방식이 놓치던 언약·메시아
    # 급소 절(예: 삼하 7:12·16)까지 덮기 위함(2026-07-15 검증 반영).
    commentary_text = None
    vc = {}
    if book_slug:
        try:
            k = min(8, max(3, len(focus_nums) // 4 + 1))   # 구간이 길수록 급소도 더 많이
            crux = openbible_xref.top_crux_verses(book, int(chapter), focus_nums, k=k)
            for cv in crux:
                c = biblehub_lookup.fetch_verse_commentary(book_slug, int(chapter), cv)
                if c:
                    vc[cv] = c
            commentary_text = biblehub_lookup.format_commentary_for_prompt(
                vc, book, int(chapter)
            )
            if commentary_text:
                log(f"  Bible Hub 주석: 급소 {len(vc)}개 절 첨부(연결개수 상위 {len(crux)})", "INFO")
        except Exception as e:
            log(f"  주석 조사 실패(주석 없이 계속): {e}", "WARN")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(qt_data, chapter, biblehub_text, chapter_verses, xref_text, commentary_text, focus_label)},
        ],
        response_format={"type": "json_object"},
        temperature=TEMPERATURE,
        seed=SEED,
        max_tokens=MAX_TOKENS,
    )
    data = json.loads(response.choices[0].message.content)
    cost = calc_cost(response.usage)
    if response.choices[0].finish_reason == "length":
        log(f"  응답이 max_tokens({MAX_TOKENS})에 걸려 잘렸을 수 있음 — key_details 누락·개수변동 주의", "WARN")

    # 스키마 최소 검증 — 어긋나면 예외로 올려 파이프라인이 KB 없이 진행하게 함
    if not isinstance(data.get("key_details"), list) or not data["key_details"]:
        raise ValueError("key_details가 비어 있거나 리스트가 아님")
    if not isinstance(data.get("인물"), list):
        raise ValueError("인물이 리스트가 아님")
    if not data.get("신학_핵심"):
        raise ValueError("신학_핵심이 비어 있음")
    data.setdefault("주의점", [])

    # 앵커(스티커) 정규화 — source를 '우리가 실제로 먹인 주석'에만 근거해 확정/강등한다.
    # 먹인 주석 꼬리표 → "저자, 책 장:절"로 확정(추적 가능), 안 먹인 주석가 이름(모델 기억)은 미확정으로 강등.
    fed_pairs, fed_authors = _build_fed_index(vc, qt_data.get("book_name", ""), chapter)
    n_anchor = n_demote = 0
    for kd in data["key_details"]:
        before = (kd.get("source") or "").strip()
        after = _normalize_source(before, fed_pairs, fed_authors)
        if after != before:
            kd["source"] = after
            if after == "일반 지식(미확정)":
                n_demote += 1
            else:
                n_anchor += 1
    if fed_pairs or n_demote:
        log(f"  근거 앵커: 확정 {n_anchor}개 · 미확정 강등 {n_demote}개", "INFO")

    # 결정적 강등 — "문화관습" 태그인데 근거가 "본문을 읽었다"뿐이면(진짜 반증 근거 없음)
    # 프롬프트 지시를 모델이 잊었더라도 코드가 자동으로 본문관찰로 되돌린다.
    # (2026-07-10: 사무엘하 4:5-6 "낮잠 문화" 오분류 이후 추가 — 한 번뿐인 개인 행동을
    #  그 시대 관습으로 일반화한 항목을 걸러낸다.)
    for kd in data["key_details"]:
        if kd.get("cat") == "문화관습" and (kd.get("source") or "").strip() in WEAK_SOURCES:
            kd["cat"] = "본문관찰"

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

    # 3) 채울 구간 결정 — '오늘 구간'이 이미 깊게 조사됐는가로 판단(구간별 누적).
    #    각 장의 _generated["passages"]에 조사 끝난 구간(예: "18-29")을 기록해 두고,
    #    오늘 구간이 거기 없으면 그 구간만 새로 조사해 기존 KB에 이어붙인다(merge).
    #    단, 재조사는 'AI가 만든 장'에만 — 손수 검증한 KB는 자동으로 안 건드린다(--force 필요).
    ai_made = set(kb.get("_generated", {}).keys())
    gen_rec = kb.get("_generated", {})

    # 오늘 각 장이 다루는 구간 절 번호 + 라벨
    passages = {c: sorted(passage_verses_in(qt_data, c)) for c in chapters}
    labels = {c: (f"{p[0]}-{p[-1]}" if p else "전체") for c, p in passages.items()}

    missing, already, locked = [], [], []
    for c in chapters:
        done = set(gen_rec.get(c, {}).get("passages", []))
        if args.force or c not in kb:
            missing.append(c)
        elif labels[c] in done:
            already.append(c)
        elif c in ai_made:
            missing.append(c)          # AI가 만든 장인데 오늘 구간은 아직 → 그 구간만 추가 조사
        else:
            locked.append(c)

    if already:
        log(f"이미 조사된 구간(건너뜀): {[f'{c}장 {labels[c]}' for c in already]}", "SKIP")
    for c in locked:
        log(f"[{book} {c}장 {labels[c]}] 손수 검증한 KB로 보여 건드리지 않습니다 (다시 만들려면 --force)", "WARN")
    if not missing:
        log("새로 조사할 구간이 없습니다 → 정상 종료(재사용)", "OK")
        return 0

    log(f"조사할 구간: {[f'{c}장 {labels[c]}' for c in missing]}")

    if args.dry_run:
        log("[DRY RUN] 실제 생성 없이 종료합니다.")
        return 0

    # 4) 생성
    try:
        client = get_client()
    except RuntimeError as e:
        log(str(e), "ERR")
        return 2

    # 기존 장을 덮어쓰기 전에 파일 통째로 한 번 백업 (되돌릴 수 있게)
    overwriting = [c for c in missing if c in kb]
    if overwriting and ref_path.exists():
        bak = ref_path.with_suffix(".json.bak")
        bak.write_text(ref_path.read_text(encoding="utf-8"), encoding="utf-8")
        log(f"덮어쓸 장 {overwriting} → 기존 KB를 {bak.name}로 백업", "INFO")

    kb.setdefault("_auto", True)
    kb.setdefault("_note", "AI 자동 생성 KB(미검증). 2주차에 신학 자료 대조·검증 예정. "
                           "confidence·source를 참고하고, 어원·정체·번역 견해차는 주의점 확인.")
    generated = kb.setdefault("_generated", {})

    total_krw = 0.0
    made = []
    for ch in missing:
        try:
            plabel = labels[ch]
            pnums = passages.get(ch, [])
            log(f"[{book} {ch}장 {plabel}] 조사 중 (model={MODEL})...")
            passage_dict, cost = generate_chapter_kb(client, qt_data, ch, pnums)
            kb[ch] = merge_chapter_kb(kb.get(ch), passage_dict, pnums)

            rec = generated.setdefault(ch, {})
            rec["at"] = datetime.now(KST).isoformat()
            rec["model"] = MODEL
            done = set(rec.get("passages", []))
            if plabel != "전체":
                done.add(plabel)
            rec["passages"] = sorted(done)

            total_krw += cost["cost_krw"]
            made.append(ch)

            # 이번 구간이 실제로 덮은 절 확인 — 빈 구간 버그가 재발하면 바로 보이게.
            cov = sorted(covered_verses(kb[ch]))
            gap = [v for v in pnums if v not in set(cov)]
            log(f"[{book} {ch}장 {plabel}] 완료 — 이번 구간 항목 {len(passage_dict['key_details'])}개 · "
                f"장 누적 {len(kb[ch]['key_details'])}개 / 인물 {len(kb[ch]['인물'])}명 / 약 {cost['cost_krw']:.1f}원", "OK")
            if gap:
                log(f"[{book} {ch}장] 오늘 구간 중 KB가 안 다룬 절: {gap}", "WARN")
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
