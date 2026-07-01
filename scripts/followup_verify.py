"""떠오르는 질문 — 2차 검증·가드 (라이브 재사용 모듈).

generate_meditation.py에서 generate_follow_up 직후 clean()을 호출한다.
호출자는 chat 함수를 넘긴다:
    chat(model, system_text, payload_dict, schema_name, schema_dict, temperature, max_tokens) -> 파싱된 dict

동작: 검증(gpt-4o) → 메인 개수 강제 → 가드(유사도 중복제거 + '왜했나' 메인 재작성) → 개수 강제.
실패하면 1차 생성본(원본)을 그대로 돌려줘 본 묵상은 깨지지 않게 한다.
"""
import difflib
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERIFY_PROMPT_PATH = ROOT / "prompts" / "follow_up_verify" / "system.md"
VERIFY_MODEL = "gpt-4o"
GUARD_MODEL = "gpt-4o"

# ===== 스키마 =====
_FU_ITEM = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "answer": {"type": "string"},
        "follow_ups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"question": {"type": "string"}, "answer": {"type": "string"}},
                "required": ["question", "answer"], "additionalProperties": False,
            },
        },
    },
    "required": ["question", "answer", "follow_ups"], "additionalProperties": False,
}
_TAIL_ITEM = {
    "type": "object",
    "properties": {"question": {"type": "string"}, "answer": {"type": "string"}},
    "required": ["question", "answer"], "additionalProperties": False,
}
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "follow_up_questions": {"type": "array", "items": _FU_ITEM},
        "report": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"slot": {"type": "string"}, "verdict": {"type": "string"}, "note": {"type": "string"}},
                "required": ["slot", "verdict", "note"], "additionalProperties": False,
            },
        },
    },
    "required": ["follow_up_questions", "report"], "additionalProperties": False,
}

# ===== 가드 판정 =====
_BANNED = re.compile(
    r"이유는?\s*무엇|왜\s|의미는?\s*무엇|어떤\s*의미|무엇을\s*의미|배경은?\s*무엇"
    r"|교훈|평가할|어떻게\s*평가|진정성|어떤\s*영향|어떻게\s*이해"
)


def needs_fix(q):
    return bool(_BANNED.search(q or ""))


def _near_dup(a, b):
    return difflib.SequenceMatcher(None, a or "", b or "").ratio() >= 0.6


FORCE_MAIN_PROMPT = """당신은 '떠오르는 질문' 교정자예요. 아래 '고칠_메인'은 "왜 했나 / 이유는 / 의미는 / 배경은" 꼴이라 5단 묵상과 겹쳐요. 이 메인 1개와 꼬리 2개를 규칙대로 다시 쓰세요.

규칙:
- 메인은 본문을 한 층 파고드는 질문으로: 어원(KB에 '어원' 자료 있을 때만)·놓친 디테일·인물의 과거나 정체·지명 중 하나.
- "왜 ~했나요 / 이유는 무엇 / 의미는 무엇 / 배경은 무엇" 표현 절대 금지. 답을 미리 흘리지 말 것.
- 반드시 그날 '본문_내용'에 실제로 나오는 단어·인물·지명만 사용. 본문에 없는 다른 장의 사건·단어 금지.
- '다른_질문들'이 다루는 소재(지명·인물·단어)와 절대 겹치지 마세요 — 완전히 다른 대상·다른 각도로.
- 원어 질문은 익숙한 번역어를 먼저 대고('깊은 잠'이라는 히브리 원어 …), '의미'보다 '원어로 어떻게 써져 있나'로.
- 답변은 2단락(본문 직접 답 → 의미·맥락), ~이에요/~거예요체, 미화 금지. 지명·소재면 현대 위치+지리+타 성경 등장을 곁들여요. 마일·규빗은 km/m로 환산.
- 인물의 죽음·심판 등 무게 있는 지점이면 '학자들은 ~로 봐요' 한 줄을 곁들여요(KB 근거, 없으면 완곡·지어내기 금지).
- 어미 ~이에요/~거예요/~었어요. 외래어·신학용어 금지.

출력: 순수 JSON {"question": "...", "answer": "...", "follow_ups": [{"question":"...","answer":"..."},{"question":"...","answer":"..."}]}"""

FORCE_TAIL_PROMPT = """당신은 '떠오르는 질문' 교정자예요. 아래 '고칠_꼬리'가 다른 질문과 겹쳐요. 부모 메인('상위_메인')의 실타래를 이어가되, '다른_질문들'의 소재와 절대 겹치지 않게 다른 단서로 다시 쓰세요.

규칙:
- 그날 '본문_내용'에 실제로 나오는 단어·인물·지명만. 본문에 없는 것 금지.
- "왜 ~했나요 / 이유는 / 의미는 / 교훈" 금지. 답을 미리 흘리지 말 것.
- '다른_질문들'이 다루는 지명·인물·단어와 겹치지 마세요 — 완전히 다른 소재.
- 원어 질문은 익숙한 번역어를 먼저 대고('깊은 잠'이라는 히브리 원어 …), '의미'보다 '원어로 어떻게 써져 있나'로.
- 답변은 2단락(본문 직접 답 → 의미·맥락), ~이에요/~거예요체, 미화 금지. 지명·소재면 현대 위치+지리+타 성경 등장을 곁들여요. 마일·규빗은 km/m로 환산. 외래어·신학용어 금지.
- 인물의 죽음·심판 등 무게 있는 지점이면 '학자들은 ~로 봐요' 한 줄을 곁들여요(KB 근거, 없으면 완곡·지어내기 금지).

출력: 순수 JSON {"question": "...", "answer": "..."}"""


# ===== 헬퍼 =====
def usable_kb(kb):
    """슬라이스 결과가 book/_note 껍데기뿐이면(해당 장 자료 없음) None."""
    if not kb:
        return None
    return kb if any(k.isdigit() for k in kb.keys()) else None


def _body_text(qt):
    return "\n".join(f"{v.get('number','')} {v.get('text','')}" for v in qt.get("verses", []))


def _enforce_count(items):
    """메인 정확히 3개 · 각 꼬리 정확히 2개로 자른다(초과분 제거)."""
    items = (items or [])[:3]
    for m in items:
        m["follow_ups"] = (m.get("follow_ups") or [])[:2]
    return items


def _valid(items):
    return len(items) == 3 and all(len(m.get("follow_ups", [])) == 2 for m in items)


def _flatten(items):
    order = []
    for mi in range(min(3, len(items))):
        order.append(("main", mi, None))
        for ti in range(min(2, len(items[mi].get("follow_ups", [])))):
            order.append(("tail", mi, ti))
    return order


def _slot_q(items, slot):
    kind, mi, ti = slot
    return items[mi]["question"] if kind == "main" else items[mi]["follow_ups"][ti]["question"]


# ===== 검증 =====
def _verify(chat, qt, kb, deep5, items):
    system = VERIFY_PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "본문_참조": qt.get("scripture_ref", ""), "본문_내용": _body_text(qt),
        "지식": kb, "이미_다룬_5단": deep5, "검수_대상": {"follow_up_questions": items},
    }
    out = chat(VERIFY_MODEL, system, payload, "verify_response", VERIFY_SCHEMA, 0.3, 6000)
    return out.get("follow_up_questions", items), out.get("report", [])


def _force_main(chat, qt, kb, deep5, main_block, others, note=None):
    payload = {
        "본문_참조": qt.get("scripture_ref", ""), "본문_내용": _body_text(qt),
        "지식": kb, "이미_다룬_5단": deep5, "고칠_메인": main_block, "다른_질문들": others,
    }
    if note:
        payload["주의"] = note
    return chat(GUARD_MODEL, FORCE_MAIN_PROMPT, payload, "main_rewrite", _FU_ITEM, 0.4, 1500)


def _force_tail(chat, qt, kb, deep5, main_q, tail_block, others, note=None):
    payload = {
        "본문_참조": qt.get("scripture_ref", ""), "본문_내용": _body_text(qt),
        "지식": kb, "이미_다룬_5단": deep5, "상위_메인": main_q, "고칠_꼬리": tail_block, "다른_질문들": others,
    }
    if note:
        payload["주의"] = note
    return chat(GUARD_MODEL, FORCE_TAIL_PROMPT, payload, "tail_rewrite", _TAIL_ITEM, 0.4, 1000)


def _run_guard(chat, qt, kb, deep5, items, log=None):
    n = min(3, len(items))
    # (1) 메인 '왜했나/막연' 재교정 (최대 3회)
    for i in range(n):
        tries = 0
        while needs_fix(items[i].get("question", "")) and tries < 3:
            others = [_slot_q(items, s) for s in _flatten(items) if not (s[0] == "main" and s[1] == i)]
            try:
                fixed = _force_main(chat, qt, kb, deep5, items[i], others)
            except Exception as e:
                if log:
                    log(f"  가드 메인 재교정 실패: {e}", "WARN")
                break
            tries += 1
            if fixed:
                items[i] = fixed
                if not needs_fix(fixed.get("question", "")):
                    break
    # (2) 전역 중복 제거 (거의 똑같은 질문만) — 새로 쓴 것도 또 겹치면 최대 2회 재시도
    seen = []
    for slot in _flatten(items):
        q = _slot_q(items, slot)
        tries = 0
        while tries < 2 and next((s for s in seen if _near_dup(q, s)), None):
            dup_of = next(s for s in seen if _near_dup(q, s))
            tries += 1
            others = [_slot_q(items, s2) for s2 in _flatten(items) if s2 != slot]
            note = f"'{dup_of[:24]}…'와 거의 같은 질문이에요. 그 소재 말고 그날 본문의 완전히 다른 것으로 새로 쓰세요."
            try:
                if slot[0] == "main":
                    fixed = _force_main(chat, qt, kb, deep5, items[slot[1]], others, note=note)
                    items[slot[1]].update({"question": fixed["question"], "answer": fixed["answer"],
                                           "follow_ups": fixed["follow_ups"]})
                else:
                    mi, ti = slot[1], slot[2]
                    fixed = _force_tail(chat, qt, kb, deep5, items[mi]["question"], items[mi]["follow_ups"][ti], others, note=note)
                    items[mi]["follow_ups"][ti].update({"question": fixed["question"], "answer": fixed["answer"]})
                q = fixed["question"]
            except Exception as e:
                if log:
                    log(f"  가드 중복 교정 실패: {e}", "WARN")
                break
        seen.append(q)
    return items


def clean(chat, qt, kb, deep5, items, log=None):
    """검증 + 가드 + 개수 강제. 실패 시 원본 반환."""
    kb = usable_kb(kb)
    orig = _enforce_count([dict(m) for m in items])
    try:
        verified, _ = _verify(chat, qt, kb, deep5, items)
        verified = _enforce_count(verified)
        if not _valid(verified):
            return orig
        guarded = _enforce_count(_run_guard(chat, qt, kb, deep5, verified, log=log))
        return guarded if _valid(guarded) else verified
    except Exception as e:
        if log:
            log(f"검증·가드 전체 실패 → 1차 생성본 유지: {e}", "WARN")
        return orig
