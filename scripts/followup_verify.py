"""떠오르는 질문 — 2차 검증·가드 (DEPRECATED, 2026-07-09부터 미사용).

followup_pool.py(후보 풀 아키텍처 v3)로 대체됨 — generate_meditation.py는 더 이상
이 모듈을 import하지 않는다. 참고용으로만 남겨둔다.
대체 이유: 이 모듈은 "일단 다 쓰고, 문제 있으면 GPT에게 다시 써달라" 방식이라
GPT 호출이 하루 최대 20~30회까지 늘 수 있고, KB에 없는 카테고리(어원 등)를
강제로 채우다 근거 없는 단정이 나오는 문제를 구조적으로 막지 못했다
(2026-07-09 사무엘하 4장 감사에서 확인). 자세한 경위는 project 메모리
project_jumanna_step2_followup 참고.

--- 이하 원래 문서 ---

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


def _history_questions(history):
    questions = []
    for row in history or []:
        if isinstance(row, str):
            q = row.strip()
        elif isinstance(row, dict):
            q = (row.get("question") or "").strip()
        else:
            q = ""
        if q:
            questions.append(q)
    return questions


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


TOPIC_MODEL = "gpt-4o-mini"
TOPIC_PROMPT = """각 질문이 '진짜로 다루는 핵심 소재'를 한 단어(또는 짧은 명사구)로 뽑아요.
- 주인공(다윗·사울·하나님 등)이 아니라, 그 질문의 실제 대상(지명·인물·사물·사건)을 고릅니다.
  예) "헤브론은 어떤 도시인가요?" → 헤브론
      "다윗은 요나단을 어떻게 불렀나요?" → 요나단
      "활 노래라는 명칭은 어디서 유래했나요?" → 활 노래
순수 JSON: {"topics": ["...", ...]}  (받은 질문 순서대로, 개수 동일하게)"""
TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"topics": {"type": "array", "items": {"type": "string"}}},
    "required": ["topics"], "additionalProperties": False,
}


def _same_topic(a, b):
    """소재 태그가 같은 소재인가 — 완전일치 또는 핵심 명사 포함관계('헤브론' ⊂ '헤브론 역사')."""
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _main_topics(chat, questions, log=None):
    """메인 질문들의 핵심 소재를 한 단어씩 태그. 실패하면 None(→ 글자비교로 대체)."""
    try:
        max_tokens = max(300, min(2500, len(questions) * 18))
        out = chat(TOPIC_MODEL, TOPIC_PROMPT, {"질문들": questions}, "topics", TOPIC_SCHEMA, 0.0, max_tokens)
        ts = out.get("topics", [])
        return ts if len(ts) == len(questions) else None
    except Exception as e:
        if log:
            log(f"소재 태그 추출 실패 → 글자비교로 대체: {e}", "WARN")
        return None


def _dedup_net(chat, qt, kb, deep5, items, log=None, history=None):
    """결정적 중복 안전망 — 검증·가드가 실패·생략돼도 '항상' 마지막에 돈다.
    메인 3개의 '소재 태그'가 겹치면(같은 지명·인물·사물) 뒤엣것을 재작성한다.
    태그를 못 얻으면 글자 유사도(≥0.75)로 대체. 재작성까지 실패하면 조용히 넘기지 않고 ERR로 크게 남긴다."""
    try:
        n = min(3, len(items))
        mains = [items[i].get("question", "") for i in range(n)]
        topics = _main_topics(chat, mains, log=log)
        for i in range(n):
            for j in range(i):
                if topics:
                    dup = _same_topic(topics[i], topics[j])
                    why = f"같은 소재 '{topics[j]}'"
                else:
                    dup = difflib.SequenceMatcher(None, mains[i], mains[j]).ratio() >= 0.75
                    why = "글자 유사"
                if not dup:
                    continue
                if log:
                    log(f"⚠ 중복 메인({why}): '{mains[j][:18]}…' ↔ '{mains[i][:18]}…' → 재작성", "ERR")
                others = [items[k].get("question", "") for k in range(len(items)) if k != i]
                note = f"'{mains[j][:24]}…'와 같은 소재예요. 그 소재 말고 그날 본문의 완전히 다른 것으로 새로 쓰세요."
                try:
                    fixed = _force_main(chat, qt, kb, deep5, items[i], others, note=note)
                    items[i].update({"question": fixed["question"], "answer": fixed["answer"],
                                     "follow_ups": fixed["follow_ups"]})
                    mains[i] = items[i]["question"]
                except Exception as e:
                    if log:
                        log(f"  중복 메인 재작성 실패 — 수동 확인 필요(중복 그대로): {e}", "ERR")
                break

        history_qs = _history_questions(history)
        if history_qs:
            slots = _flatten(items)
            current_qs = [_slot_q(items, slot) for slot in slots]
            topics = _main_topics(chat, current_qs + history_qs, log=log)
            current_topics = topics[:len(current_qs)] if topics else None
            history_topics = topics[len(current_qs):] if topics else None

            for idx, slot in enumerate(slots):
                q = _slot_q(items, slot)
                tries = 0
                while tries < 2:
                    dup_idx = None
                    why = ""
                    if current_topics and history_topics:
                        for hidx, htopic in enumerate(history_topics):
                            if _same_topic(current_topics[idx], htopic):
                                dup_idx = hidx
                                why = f"기존 소재 '{htopic}'"
                                break
                    else:
                        for hidx, hq in enumerate(history_qs):
                            if difflib.SequenceMatcher(None, q, hq).ratio() >= 0.72:
                                dup_idx = hidx
                                why = "기존 질문과 글자 유사"
                                break
                    if dup_idx is None:
                        break

                    tries += 1
                    past_q = history_qs[dup_idx]
                    if log:
                        log(f"⚠ 기존 JSON 중복({why}): '{past_q[:18]}…' ↔ '{q[:18]}…' → 재작성", "ERR")
                    others = [_slot_q(items, other) for other in slots if other != slot] + history_qs[:80]
                    note = (
                        f"같은 성경책의 기존 STEP 2 질문 '{past_q[:40]}…'와 소재/맥락이 겹쳐요. "
                        "그 소재를 다시 묻지 말고 오늘 본문 안의 완전히 다른 신규 소재로 쓰세요."
                    )
                    try:
                        if slot[0] == "main":
                            fixed = _force_main(chat, qt, kb, deep5, items[slot[1]], others, note=note)
                            items[slot[1]].update({
                                "question": fixed["question"],
                                "answer": fixed["answer"],
                                "follow_ups": fixed["follow_ups"],
                            })
                        else:
                            mi, ti = slot[1], slot[2]
                            fixed = _force_tail(
                                chat, qt, kb, deep5, items[mi]["question"],
                                items[mi]["follow_ups"][ti], others, note=note,
                            )
                            items[mi]["follow_ups"][ti].update({
                                "question": fixed["question"],
                                "answer": fixed["answer"],
                            })
                        q = fixed["question"]
                    except Exception as e:
                        if log:
                            log(f"  기존 JSON 중복 재작성 실패 — 수동 확인 필요(중복 그대로): {e}", "ERR")
                        break
    except Exception as e:
        if log:
            log(f"중복 안전망 오류: {e}", "WARN")
    return items


def clean(chat, qt, kb, deep5, items, history=None, log=None):
    """검증 + 가드 + 개수 강제 + 결정적 중복 안전망. 각 단계 격리(한 곳 실패해도 직전 결과 유지)."""
    kb = usable_kb(kb)
    result = _enforce_count([dict(m) for m in items])   # 기본값 = 1차 생성본
    # 1) 검증
    try:
        verified, _ = _verify(chat, qt, kb, deep5, items)
        verified = _enforce_count(verified)
        if _valid(verified):
            result = verified
    except Exception as e:
        if log:
            log(f"검증 실패 → 직전 단계 유지: {e}", "WARN")
    # 2) 가드 (실패해도 검증 결과는 살림)
    try:
        guarded = _enforce_count(_run_guard(chat, qt, kb, deep5, result, log=log))
        if _valid(guarded):
            result = guarded
    except Exception as e:
        if log:
            log(f"가드 실패 → 직전 단계 유지: {e}", "WARN")
    # 3) 결정적 중복 안전망 (항상 실행 — 검증·가드가 실패·생략돼도 중복은 여기서 잡음)
    result = _dedup_net(chat, qt, kb, deep5, result, log=log, history=history)
    return result if _valid(result) else _enforce_count([dict(m) for m in items])
