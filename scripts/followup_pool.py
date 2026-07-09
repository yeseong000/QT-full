"""떠오르는 질문 — 후보 풀 아키텍처 (v3).

기존(generate_follow_up + followup_verify.clean)은 "일단 9개를 완성해서 뽑고,
문제가 보이면 그 부분만 GPT에게 다시 써달라고 요청"하는 방식이었다. 이 모듈은
그 대신 "후보를 넉넉히 만들고, 코드가 결정적으로 9개를 고르고, 고른 것만 답을
쓰게" 하는 방식으로 바꾼다.

흐름:
    1) 그날 KB 커버리지 확인 → 실제로 자료가 있는 카테고리만 후보 요청
    2) 후보 생성 (GPT 1회, 카테고리·개수 미달이면 배치 통째로 재시도)
    3) 결정적 선택 — 카테고리를 순환하며 중복 아닌 후보로 9개를 채움 (GPT 호출 없음)
    4) 메인3+꼬리6 트리 구성 (GPT 호출 없음)
    5) 선택된 9개만 답변 생성 (GPT 1회)
    6) 독립 그라운딩(근거) 검수 — 생성에 관여 안 한 별도 판정 (GPT 1회)
    7) 근거 부족 슬롯만 후보 풀에서 교체 후 그 슬롯만 재검수 (최대 2라운드)

카테고리는 "매일 정확히 9개 중 1개씩"을 강제하지 않는다. 2026-07-09 사무엘하
4장 감사에서, KB에 어원·문화관습 자료가 0개인데도 그 카테고리를 억지로 채우다
근거 없는 단정이 나온 것을 확인했다 — 그래서 그날 KB가 뒷받침하는 카테고리만
요청하고, 선택은 카테고리 균형이 아니라 "중복 없는 좋은 질문 9개"에 집중한다.
"""
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
PARTS_DIR = ROOT / "prompts" / "follow_up" / "parts"
POOL_PROMPT_DIR = ROOT / "prompts" / "follow_up_pool"
GROUNDING_PROMPT_PATH = ROOT / "prompts" / "follow_up_grounding" / "system.md"

CATEGORIES = (
    "주석형/본문관찰", "지명 정보", "어원·유래", "인물 배경", "문화·관습",
    "신학/해석 견해", "본문 디테일", "연결 질문", "랜덤",
)
# KB key_details의 cat 값(어원/지리/문화관습·문화/신학핵심)과 STEP2 카테고리 매핑.
# "신학/해석 견해"는 항상 존재하는 챕터 top-level 필드(신학_핵심·주의점)로도 채워짐.
KB_CAT_PREFIX = {"지명 정보": "지리", "어원·유래": "어원", "문화·관습": "문화", "신학/해석 견해": "신학"}
# 그날 본문 텍스트만으로 항상 채울 수 있는 카테고리 — KB 유무와 무관하게 매일 요청.
ALWAYS_FILLABLE = ("주석형/본문관찰", "인물 배경", "본문 디테일", "연결 질문", "랜덤")
# 메인 후보로 우선 배치할 카테고리(주제를 여는 느낌에 가까운 순서).
MAIN_PREFERRED = ("주석형/본문관찰", "인물 배경", "연결 질문", "본문 디테일", "신학/해석 견해")

# 카테고리당 후보 개수를 고정하지 않는다 — 그날 KB가 풍부한 카테고리는 더 많이,
# 얇은 카테고리는 최소한만 요청한다. MAX로 한쪽이 너무 쏠리지 않게 막는다.
MIN_CANDIDATES_PER_CATEGORY = 2
MAX_CANDIDATES_PER_CATEGORY = 6
DEFAULT_ALWAYS_FILLABLE_QUOTA = 3   # KB 커버리지 신호가 없는 5개 카테고리의 기본값
MAX_FINAL_PER_CATEGORY = 3          # 최종 9개 중 한 카테고리가 차지할 수 있는 최대 개수
MAX_CANDIDATE_ATTEMPTS = 4
MAX_ANSWER_ATTEMPTS = 3
MAX_GROUNDING_ROUNDS = 1
MIN_KB_MATERIAL = 1

# 후보는 아직 답변 없는 질문 문구뿐이라 상대적으로 위험이 낮다 — mini로 비용을 크게
# 줄인다. 실제 신학 내용이 걸리는 답변 작성·그라운딩 검수는 4o를 유지한다.
CANDIDATE_MODEL = "gpt-4o-mini"
ANSWER_MODEL = "gpt-4o"
GROUNDING_MODEL = "gpt-4o"

_ZERO_COST = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "cost_krw": 0.0}
_ROLE_IDS = ["m1", "t1a", "t1b", "m2", "t2a", "t2b", "m3", "t3a", "t3b"]


class FollowUpPoolError(Exception):
    """후보 풀 파이프라인이 재시도 끝에 완전히 실패했을 때."""


class PoolSelectionError(Exception):
    """이번 배치의 후보로는 9개를 못 채웠을 때 — 배치를 통째로 재생성하라는 신호."""


def _add_cost(total, cost):
    for k in total:
        total[k] = round(total[k] + (cost or {}).get(k, 0), 6)


def _read(path):
    return path.read_text(encoding="utf-8").strip()


def _body_text(qt):
    return "\n".join(f"{v.get('number', '')} {v.get('text', '')}" for v in qt.get("verses", []))


def _iter_all(tree):
    for m in tree:
        yield m
        for t in m["follow_ups"]:
            yield t


# ===== 1. 그날 KB 커버리지 → 활성 카테고리 =====
def count_kb_coverage(kb: dict | None) -> dict[str, int]:
    """카테고리별(KB 의존 4개) 실측 근거 자료 개수. kb는 slice_kb_to_passage() 결과."""
    counts = {c: 0 for c in KB_CAT_PREFIX}
    if not kb:
        return counts
    for key, chap in kb.items():
        if not isinstance(key, str) or not key.isdigit() or not isinstance(chap, dict):
            continue  # book/_note/_auto/_generated 등 메타 키 skip
        for kd in chap.get("key_details") or []:
            cat = (kd or {}).get("cat") or ""
            for label, prefix in KB_CAT_PREFIX.items():
                if prefix in cat:
                    counts[label] += 1
        if (chap.get("신학_핵심") or "").strip():
            counts["신학/해석 견해"] += 1
        counts["신학/해석 견해"] += len(chap.get("주의점") or [])
    return counts


def resolve_active_categories(kb: dict | None, *, min_material: int = MIN_KB_MATERIAL):
    """오늘 후보를 요청할 카테고리 목록. 본문만으로 항상 채울 수 있는 5개는 무조건
    포함하고, KB 의존 4개는 그날 실측 자료가 있을 때만 포함한다. 카테고리 개수는
    날마다 5~9개로 달라질 수 있다 — 그 자체가 이 설계의 핵심이다."""
    coverage = count_kb_coverage(kb)
    active = [c for c in CATEGORIES if c in ALWAYS_FILLABLE or coverage.get(c, 0) >= min_material]
    dropped = [c for c in KB_CAT_PREFIX if c not in active]
    return active, dropped, coverage


def resolve_category_quotas(active_categories, coverage: dict[str, int]) -> dict[str, int]:
    """카테고리마다 정확히 같은 개수를 요청하지 않는다 — KB 자료가 풍부한 카테고리는
    더 많이, 얇은 카테고리는 최소한만 요청한다(MIN~MAX 사이로 캡을 씌워 한쪽으로
    너무 쏠리지 않게 한다). ALWAYS_FILLABLE 5개는 KB 커버리지 신호가 없으므로
    고정 기본값을 쓴다."""
    quotas = {}
    for cat in active_categories:
        if cat in KB_CAT_PREFIX:
            richness = coverage.get(cat, 0)
            quotas[cat] = max(MIN_CANDIDATES_PER_CATEGORY, min(MAX_CANDIDATES_PER_CATEGORY,
                                                                 MIN_CANDIDATES_PER_CATEGORY + richness))
        else:
            quotas[cat] = DEFAULT_ALWAYS_FILLABLE_QUOTA
    return quotas


# ===== 2. 후보 생성 (GPT 1회) =====
def build_candidate_system_prompt(category_counts: dict[str, int]) -> str:
    wrapper = _read(POOL_PROMPT_DIR / "candidate_system.md")
    tone = _read(PARTS_DIR / "01_role_tone.md")
    rules = _read(PARTS_DIR / "03_question_rules.md")
    total = sum(category_counts.values())
    quota_lines = "\n".join(f"- {cat}: 정확히 {n}개" for cat, n in category_counts.items())
    quota_block = (
        "## 오늘 지킬 카테고리 목록과 개수 (최종 기준 — 위 공유 규칙 중 '9개 카테고리 구성' 설명은 "
        "예전 방식이니 무시한다)\n\n" + quota_lines +
        f"\n\n**총 {total}개를 반드시 전부 만든다.** 이 목록에 없는 카테고리는 만들지 않는다. "
        "모든 카테고리를 다 채워야 한다는 규칙은 더 이상 적용되지 않는다 — 그날 KB에 자료가 있는 "
        f"카테고리만 요청된 것이다. 개수가 모자라면 실패로 처리되니, 카테고리별 개수를 정확히 맞춰 "
        f"총 {total}개를 채운다."
    )
    return "\n\n---\n\n".join([wrapper, tone, rules, quota_block])


def _candidate_schema(category_counts: dict[str, int]) -> dict:
    total = sum(category_counts.values())
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "minItems": total,
                "maxItems": total,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "category": {"type": "string", "enum": sorted(category_counts)},
                        "topic": {"type": "string"},
                        "source": {"type": "string"},
                        "group_hint": {"type": "string"},
                    },
                    "required": ["question", "category", "topic", "source", "group_hint"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }


def generate_candidate_pool(chat, qt, kb, category_counts, history, deep5, *, attempt, total_cost):
    """category_counts: {카테고리: 개수} — 카테고리마다 다른 개수를 요청할 수 있다
    (resolve_category_quotas() 참고). 균등 배분이 필요하면 호출부에서 만들어 넘긴다."""
    system = build_candidate_system_prompt(category_counts)
    payload = {
        "본문_참조": qt.get("scripture_ref", ""),
        "본문_내용": _body_text(qt),
        "오륜_질문": qt.get("oryun_questions", []),
        "지식": kb,
        "같은_책_기존_STEP2_질문": history,
        "이미_다룬_5단": deep5,
        "카테고리별_요청_개수": category_counts,
        "요청_총합": sum(category_counts.values()),
        "시도_번호": attempt,
    }
    data, cost = chat(CANDIDATE_MODEL, system, payload, "candidate_pool",
                       _candidate_schema(category_counts), 0.75, 7500)
    _add_cost(total_cost, cost)
    return data.get("candidates") or []


# ===== 3. 결정적 선택 (GPT 호출 없음) =====
_WORD_RE = re.compile(r"[^\w가-힣]")


def _norm(s):
    return _WORD_RE.sub("", (s or "").lower())


def _overlap(a, b):
    """포함 관계를 겹침으로 보되, 둘 다 4자 이상일 때만 — 안 그러면 "다윗"처럼
    짧은 고유명사가 그 이름이 들어간 모든 과거 질문과 오탐 매칭된다."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if len(na) < 4 or len(nb) < 4:
        return False
    return na in nb or nb in na


def _lcs_ratio_max(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    prev = [0] * (len(nb) + 1)
    best = 0
    for i in range(1, len(na) + 1):
        curr = [0] * (len(nb) + 1)
        for j in range(1, len(nb) + 1):
            if na[i - 1] == nb[j - 1]:
                curr[j] = prev[j - 1] + 1
                best = max(best, curr[j])
        prev = curr
    return best / max(len(na), len(nb))  # 짧은 쪽이 아니라 긴 쪽으로 나눈다 — 위와 같은 이유


def _same_context(a, b):
    return _overlap(a, b) or _lcs_ratio_max(a, b) >= 0.48


# 프롬프트가 "왜/이유" 금지를 지시해도(03_question_rules.md) 실측해보니 후보 생성
# 단계에서 종종 어겨진다 — 그래서 프롬프트에만 맡기지 않고 선택 단계에서 코드로
# 걸러낸다. followup_verify.py의 _BANNED 규칙과 동일한 패턴을 재사용.
_BANNED_PATTERN = re.compile(
    r"이유는?\s*무엇|왜\s|의미는?\s*무엇|어떤\s*의미|무엇을\s*의미|배경은?\s*무엇"
    r"|교훈|평가할|어떻게\s*평가|진정성|어떤\s*영향|어떻게\s*이해"
)


def _is_banned_pattern(candidate) -> bool:
    return bool(_BANNED_PATTERN.search(candidate.get("question") or ""))


def _is_duplicate(candidate, selected, history):
    if _is_banned_pattern(candidate):
        return True
    topic = candidate.get("topic") or candidate.get("question", "")
    q = candidate.get("question", "")
    for row in selected:
        rtopic = row.get("topic") or row.get("question", "")
        if _same_context(topic, rtopic) or _same_context(q, row.get("question", "")):
            return True
    for row in history:  # history 항목은 {date, question}뿐 — topic 태그가 없다
        rq = row.get("question", "")
        if _same_context(topic, rq) or _same_context(q, rq):
            return True
    return False


def select_nine(candidates, active_categories, history, *, max_per_category=MAX_FINAL_PER_CATEGORY):
    """카테고리 균형을 강제로 맞추진 않지만, 한 카테고리가 최종 9개를 너무 많이
    차지하지 않도록 max_per_category로 캡을 씌운다. 활성 카테고리를 순환하며
    중복 아닌 후보를 하나씩 채우고, 9개가 찰 때까지 반복한다."""
    by_cat = {cat: [c for c in candidates if c.get("category") == cat] for cat in active_categories}
    cursor = {cat: 0 for cat in active_categories}
    picked_count = {cat: 0 for cat in active_categories}
    selected = []
    while len(selected) < 9:
        picked_this_round = False
        for cat in active_categories:
            if picked_count[cat] >= max_per_category:
                continue
            pool = by_cat[cat]
            while cursor[cat] < len(pool):
                cand = pool[cursor[cat]]
                cursor[cat] += 1
                if not _is_duplicate(cand, selected, history):
                    selected.append(cand)
                    picked_count[cat] += 1
                    picked_this_round = True
                    break
            if len(selected) >= 9:
                break
        if not picked_this_round:
            raise PoolSelectionError(f"9개를 못 채움 (선택 {len(selected)}개, 후보 {len(candidates)}개)")
    return selected[:9]


# ===== 4. 트리 구성 — 메인3 + 꼬리6 (GPT 호출 없음) =====
def _pick_main_seeds(selected):
    used = set()
    seeds = []
    for cat in MAIN_PREFERRED:
        for i, c in enumerate(selected):
            if i in used:
                continue
            if c.get("category") == cat:
                seeds.append(i)
                used.add(i)
                break
        if len(seeds) == 3:
            break
    i = 0
    while len(seeds) < 3 and i < len(selected):
        if i not in used:
            seeds.append(i)
            used.add(i)
        i += 1
    return seeds


def build_tree(selected):
    """group_hint(없으면 topic·question)로 남은 6개를 세 메인에 나눠 붙인다 —
    완벽한 주제 클러스터링을 보장하진 않지만, 카테고리 라벨에 얽매이지 않고
    비슷한 소재끼리 자연스럽게 묶는 결정적(재현 가능한) 방법이다."""
    seed_idxs = _pick_main_seeds(selected)
    groups = [[i] for i in seed_idxs]
    remaining = [i for i in range(len(selected)) if i not in seed_idxs]
    for i in remaining:
        cand = selected[i]
        cand_key = cand.get("group_hint") or cand.get("topic") or cand.get("question", "")
        scores = []
        for g in groups:
            seed = selected[g[0]]
            seed_key = seed.get("group_hint") or seed.get("topic") or seed.get("question", "")
            scores.append(_lcs_ratio_max(cand_key, seed_key))
        for gi in sorted(range(3), key=lambda gi: -scores[gi]):
            if len(groups[gi]) < 3:
                groups[gi].append(i)
                break

    tree = []
    rid_iter = iter(_ROLE_IDS)
    for g in groups:
        main_i, *tail_is = g
        main_rid = next(rid_iter)
        tails = []
        for t in tail_is:
            trid = next(rid_iter)
            tails.append({"role_id": trid, "question": selected[t]["question"],
                          "category": selected[t]["category"], "topic": selected[t].get("topic")})
        tree.append({"role_id": main_rid, "question": selected[main_i]["question"],
                     "category": selected[main_i]["category"], "topic": selected[main_i].get("topic"),
                     "follow_ups": tails})
    return tree


# ===== 5. 답변 생성 (GPT 1회, 선택된 것만) =====
def build_answer_system_prompt() -> str:
    wrapper = _read(POOL_PROMPT_DIR / "answer_system.md")
    tone = _read(PARTS_DIR / "01_role_tone.md")
    rules = _read(PARTS_DIR / "04_answer_rules.md")
    return "\n\n---\n\n".join([wrapper, tone, rules])


def _flatten_tree(tree):
    out = []
    for m in tree:
        out.append((m["role_id"], m["question"], m["category"]))
        for t in m["follow_ups"]:
            out.append((t["role_id"], t["question"], t["category"]))
    return out


def _answer_schema(role_ids):
    return {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role_id": {"type": "string", "enum": role_ids},
                        "answer": {"type": "string"},
                    },
                    "required": ["role_id", "answer"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["answers"],
        "additionalProperties": False,
    }


def _validate_answers(answers, expected_ids):
    if set(answers) != set(expected_ids):
        raise ValueError(f"답변 role_id 불일치: 받음={sorted(answers)} 기대={sorted(expected_ids)}")
    for rid, ans in answers.items():
        if not isinstance(ans, str) or ans.count("\n\n") != 1:
            raise ValueError(f"{rid} 답변이 2단락(\\n\\n 정확히 1회)이 아님")
        if not (180 <= len(ans) <= 600):
            raise ValueError(f"{rid} 답변 길이 이상함: {len(ans)}자")


def write_answers(chat, qt, kb, deep5, tree, total_cost, *, only_role_ids=None):
    targets = [t for t in _flatten_tree(tree) if only_role_ids is None or t[0] in only_role_ids]
    role_ids = [t[0] for t in targets]
    system = build_answer_system_prompt()
    payload = {
        "본문_참조": qt.get("scripture_ref", ""), "본문_내용": _body_text(qt),
        "지식": kb, "이미_다룬_5단": deep5,
        "질문_목록": [{"role_id": r, "question": q, "카테고리": c} for r, q, c in targets],
    }
    last_err = None
    for _ in range(MAX_ANSWER_ATTEMPTS):
        data, cost = chat(ANSWER_MODEL, system, payload, "followup_answers",
                           _answer_schema(role_ids), 0.5, 6000)
        _add_cost(total_cost, cost)
        answers = {a.get("role_id"): a.get("answer") for a in data.get("answers", []) if isinstance(a, dict)}
        try:
            _validate_answers(answers, role_ids)
            return answers
        except ValueError as e:
            last_err = e
    raise FollowUpPoolError(f"답변 생성 검증 실패: {last_err}")


def _apply_answers(tree, answers):
    """answers에 없는 role_id는 건드리지 않는다 — replace_flagged가 일부만 넘길 때 대비."""
    for m in tree:
        if m["role_id"] in answers:
            m["answer"] = answers[m["role_id"]]
        for t in m["follow_ups"]:
            if t["role_id"] in answers:
                t["answer"] = answers[t["role_id"]]


# ===== 6. 독립 그라운딩(근거) 검수 (GPT 1회) =====
_GROUNDING_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role_id": {"type": "string"},
                    "grounding": {"type": "string", "enum": [
                        "KB_또는_본문_근거있음", "본문에서_직접_확인가능",
                        "추정성_표현으로_완화됨", "근거없이_단정함",
                    ]},
                    "unsupported_claims": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"},
                },
                "required": ["role_id", "grounding", "unsupported_claims", "note"],
                "additionalProperties": False,
            },
        },
        "overall_verdict": {"type": "string", "enum": ["신뢰가능", "부분수정필요", "재검토필요"]},
        "overall_note": {"type": "string"},
    },
    "required": ["findings", "overall_verdict", "overall_note"],
    "additionalProperties": False,
}


def run_grounding_check(chat, qt, kb, tree, total_cost, *, only_role_ids=None):
    slots = [{"role_id": m["role_id"], "question": m["question"], "answer": m.get("answer", "")}
             for m in _iter_all(tree) if only_role_ids is None or m["role_id"] in only_role_ids]
    system = _read(GROUNDING_PROMPT_PATH)
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": _body_text(qt),
               "KB": kb, "검수_대상": slots}
    data, cost = chat(GROUNDING_MODEL, system, payload, "grounding_check", _GROUNDING_SCHEMA, 0.1, 5000)
    _add_cost(total_cost, cost)
    return data


TOPUP_PER_CATEGORY = 2


def _apply_pick(slot, pick, used_questions, log=None):
    if log:
        log(f"  그라운딩 대체: {slot['role_id']} '{slot['question'][:20]}…' → '{pick['question'][:20]}…'", "WARN")
    slot["question"] = pick["question"]
    slot["category"] = pick["category"]
    slot["topic"] = pick.get("topic")
    slot.pop("answer", None)
    used_questions.append(pick)


# ===== 7. 풀에서 교체 (근거 부족 슬롯만) =====
def replace_flagged(chat, qt, kb, deep5, tree, flagged_role_ids, candidates, history, total_cost, log=None):
    # "이미 쓰인 질문"은 트리의 현재 상태에서 매번 새로 계산한다 — 그라운딩 라운드가
    # 여러 번 돌 때, 이전 라운드가 이미 골라 쓴 대체 후보를 다음 라운드가 모른 채
    # 또 골라버리면 서로 다른 슬롯에 같은 질문이 중복 배치된다(실측으로 확인된 버그).
    used_questions = [{"question": m["question"], "topic": m.get("topic")} for m in _iter_all(tree)]
    role_lookup = {m["role_id"]: m for m in _iter_all(tree)}
    replaced_ids = []
    still_needed = []

    def _pick_from_pool():
        used_texts = {u["question"] for u in used_questions}
        return next((c for c in candidates
                     if c.get("question") not in used_texts and not _is_duplicate(c, used_questions, history)),
                    None)

    for rid in flagged_role_ids:
        slot = role_lookup.get(rid)
        if slot is None:
            continue
        pick = _pick_from_pool()
        if pick is None:
            still_needed.append(slot)
            continue
        _apply_pick(slot, pick, used_questions, log)
        replaced_ids.append(rid)

    # 풀이 소진돼도 그냥 포기하지 않는다 — 부족한 카테고리만 mini로 소량(카테고리당
    # TOPUP_PER_CATEGORY개) 보충해서 한 번 더 시도한다. 평소(풀이 안 마르는 날)엔
    # 이 경로를 안 타서 추가 비용이 없고, KB가 얇아 후보가 금방 바닥나는 날에만
    # 저렴하게 안전망 역할을 한다.
    if still_needed:
        needed_categories = sorted({slot["category"] for slot in still_needed})
        if log:
            log(f"  후보 풀 소진 — 부족한 카테고리 보충 생성: {needed_categories}", "WARN")
        topup_counts = {cat: TOPUP_PER_CATEGORY for cat in needed_categories}
        topup = generate_candidate_pool(chat, qt, kb, topup_counts, history, deep5, attempt=0, total_cost=total_cost)
        candidates.extend(c for c in topup if isinstance(c, dict))
        for slot in still_needed:
            pick = _pick_from_pool()
            if pick is None:
                if log:
                    log(f"  그라운딩 대체 실패(보충 후에도 소진) — {slot['role_id']} 원본 답변 유지", "ERR")
                continue
            _apply_pick(slot, pick, used_questions, log)
            replaced_ids.append(slot["role_id"])

    if replaced_ids:
        new_answers = write_answers(chat, qt, kb, deep5, tree, total_cost, only_role_ids=set(replaced_ids))
        _apply_answers(tree, new_answers)
    return tree, replaced_ids


# ===== 오케스트레이션 =====
def run_pipeline(chat, qt_data, kb, deep5, *, history=None, log=None):
    history = history or []
    total_cost = dict(_ZERO_COST)

    active_categories, dropped, coverage = resolve_active_categories(kb)
    if dropped and log:
        log(f"KB 근거 없음 → 카테고리 제외: {dropped}", "WARN")

    # 배치를 통째로 버리고 다시 굴리는 대신, 시도마다 후보를 누적한다 — 짧은 장(예:
    # 12절짜리 사무엘하 4장)은 한 배치(카테고리당 4개)만으로 9개의 서로 다른 소재가
    # 안 나올 수 있는데, 그렇다고 매번 처음부터 다시 굴리면 같은 얕은 풀만 반복
    # 생성될 뿐이다. 여러 시도의 후보를 합쳐야 실질적으로 소재가 늘어난다.
    category_counts = resolve_category_quotas(active_categories, coverage)
    if log:
        log(f"  카테고리별 요청 개수(KB 풍부도 비례): {category_counts}", "INFO")

    all_candidates = []
    selected, attempt = None, 0
    for attempt in range(1, MAX_CANDIDATE_ATTEMPTS + 1):
        batch = generate_candidate_pool(
            chat, qt_data, kb, category_counts, history, deep5, attempt=attempt, total_cost=total_cost,
        )
        batch = [c for c in batch if isinstance(c, dict)]
        all_candidates.extend(batch)
        if log:
            got = dict(Counter(c.get("category") for c in batch))
            log(f"  후보 생성 시도 {attempt}: {len(batch)}개 {got} (누적 {len(all_candidates)}개)", "INFO")
        try:
            selected = select_nine(all_candidates, active_categories, history)
            break
        except PoolSelectionError as e:
            if log:
                log(f"  선택 실패(시도 {attempt}, 누적 {len(all_candidates)}개): {e}", "WARN")
    candidates = all_candidates
    if not selected:
        raise FollowUpPoolError(f"{MAX_CANDIDATE_ATTEMPTS}번 시도했지만(누적 {len(all_candidates)}개) 9개를 채우지 못함")

    tree = build_tree(selected)
    answers = write_answers(chat, qt_data, kb, deep5, tree, total_cost)
    _apply_answers(tree, answers)

    # 매 교체 뒤에는 반드시 다시 검수한다 — 마지막 교체 라운드를 검증 없이 그냥
    # 내보내면(이전 버그) 방금 바꿔 넣은 답이 근거 있는지 아무도 확인하지 않은 채
    # 최종본에 들어간다.
    grounding_rounds = 0
    report = run_grounding_check(chat, qt_data, kb, tree, total_cost)
    grounding_rounds += 1
    flagged_findings = [f for f in report.get("findings", []) if f.get("grounding") == "근거없이_단정함"]
    for _ in range(MAX_GROUNDING_ROUNDS):
        flagged = [f["role_id"] for f in flagged_findings]
        if not flagged:
            break
        if log:
            log(f"  그라운딩 검수 {grounding_rounds}회차: 근거 부족 {len(flagged)}건 → 풀에서 교체", "WARN")
            for f in flagged_findings:
                claims = " / ".join(f.get("unsupported_claims") or [])[:200]
                log(f"    - {f['role_id']}: {f.get('note', '')[:80]} :: {claims}", "WARN")
        tree, replaced = replace_flagged(chat, qt_data, kb, deep5, tree, flagged, candidates, history,
                                          total_cost, log=log)
        if not replaced:
            break
        report = run_grounding_check(chat, qt_data, kb, tree, total_cost)
        grounding_rounds += 1
        flagged_findings = [f for f in report.get("findings", []) if f.get("grounding") == "근거없이_단정함"]

    unresolved = [f["role_id"] for f in flagged_findings]
    if unresolved and log:
        log(f"  그라운딩 미해결(재시도 소진) — 원본 답변 그대로 저장됨: {unresolved}", "ERR")

    items = [
        {"question": m["question"], "answer": m["answer"],
         "follow_ups": [{"question": t["question"], "answer": t["answer"]} for t in m["follow_ups"]]}
        for m in tree
    ]
    meta = {
        "generation_method": "candidate_pool_v3",
        "candidate_attempts": attempt,
        "candidate_pool_count": len(candidates or []),
        "dropped_categories": dropped,
        "kb_coverage": coverage,
        "grounding_rounds": grounding_rounds,
        "grounding_unresolved": unresolved,
        "category_map": [
            {"role_id": m["role_id"], "category": m["category"], "topic": m.get("topic"), "question": m["question"]}
            for m in _iter_all(tree)
        ],
    }
    return items, total_cost, meta
