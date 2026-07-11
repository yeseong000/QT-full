"""떠오르는 질문 — 단순 아키텍처 v3 (실험용, 운영 아님).

사용자 확정 설계: "질문은 싸게 잔뜩 만들어 거르고, 답변은 살아남은 9개에만 쓴다."

흐름 (딱 4단계):
    ① 질문 뽑기   — mini로 6묶음(메인6·꼬리12 = 후보 18개), 답변 없이. 싸다.
    ② 거르기      — "독자가 이미 아는 것"과 겹치면 탈락. 출처 3군데:
                     [체1] 지난 질문(과거 날짜)        … 코드(글자)
                     [체2] 오늘 질문끼리(+메인에 꼬리 포함) … 코드(글자) + mini(뜻)
                     [체3] 이미 읽은 본문 구절·5단 묵상 … mini(뜻)  ← 다윗 나이(5:4)류 여기서 탈락
    ③ 좋은 9개    — 가장 깨끗한 3묶음 선택(=9개). 남은 문제만 mini로 교체.
    ④ 답변 쓰기   — 확정 9개에만 4o로 1회(fp.write_answers=검증·재시도 내장).

코드가 하는 것: 명백한 글자 중복(체1, 체2 표면). mini가 하는 것: 뜻을 읽어야 아는 것
(체2의 '메인에 꼬리 포함', 체3의 본문·5단 재진술). 비싼 답변(4o)은 질문이 다 깨끗해진
뒤 마지막에 딱 한 번 → 교체 때문에 헛돌아도 버려지는 건 값싼 질문(mini)뿐.
"""
import re
from collections import Counter

import followup_pool as fp

PARTS_DIR = fp.PARTS_DIR

Q_MODEL = "gpt-4o"           # 질문 후보 생성 (구체·구별되는 질문 위해 4o. 판정/교체는 mini 유지)
JUDGE_MODEL = "gpt-4o-mini"  # 체3(+체2 포함) 알맹이/재진술 판정
QFIX_MODEL = "gpt-4o-mini"   # 걸린 질문 교체
# 답변은 fp.write_answers가 gpt-4o로 쓴다(검증+재시도 내장).

NUM_CANDIDATE_MAINS = 6      # 후보 묶음 수 (6묶음 = 18개 질문)
SELECT_MAINS = 3             # 최종 선택 묶음 수 (3묶음 = 9개)

_ZERO_COST = fp._ZERO_COST
_ROLE_IDS = fp._ROLE_IDS
_GOOD = "좋음"
_JUDGE_VERDICTS = [_GOOD, "본문재진술", "5단재진술", "메인에포함", "얕음"]


# ===== 프롬프트 =====
_Q_WRAPPER = """# 떠오르는 질문 — 질문 후보 생성기 (질문만, 답변 없음)

오늘 본문·KB에 근거해 **메인 질문 6개**와 각 메인의 **꼬리 질문 2개씩(총 18개 후보)**을 만든다. **답변은 만들지 않는다** — 질문 문장만. 이 18개 중 서로 다른 지식을 주는 9개만 최종 선택되니, 넉넉하고 다양하게 만든다.

## 목표 — 각 질문은 '서로 다른 새 지식'을 준다 (가장 중요)
이 질문들의 존재 이유는 독자가 **유효한 지식을 새로 얻어 본문 이해를 넓히는 것**이다. 그러니 **답을 썼을 때 서로 다른 지식이 나오는** 질문들로 채운다.
- **같은 사건·인물을 여러 각도로 파지 마라.** 예: "레갑·바아나의 문화적 배경?" "그들의 동기?" "그들의 행동에 대한 반응?" — 문장은 달라도 답이 다 '레갑·바아나가 이스보셋을 죽인 일'로 겹친다. 이런 건 **하나면 충분**하다.
- 한 소재에 2개 이상 쓰지 않는다. KB에 어원·지명 자료가 있으면 **그 각도를 아깝게 버리지 말고 꼭 하나씩 넣는다**(없으면 억지로 안 만든다).

## 두루뭉술 금지 — 본문의 '구체적 단어·행동'을 콕 집어라 (매우 중요)
"~의 **의미**는?" "~의 **영향**은?" "~의 **변화**는?" 같은 두루뭉술한 질문은 **답이 서로 겹치고 본문에 딱 붙지 않는다** — 절대 이런 걸로 채우지 마라. 대신 **본문에 실제 나온 구체적 단어·표현·행동·숫자·대비**를 하나 콕 집어 물어라. 본문은 짧아 보여도 파고들면 서로 다른 지점이 열 개 넘게 나온다.
- ✗ "다윗 통치의 의미는?" / "약속이 통치에 미친 영향은?" / "즉위가 이스라엘에 준 영향은?" (두루뭉술, 답 겹침)
- ✓ 본문에 나온 특정 단어를 집는다: "본문이 다윗을 왕의 '골육'이라 부른 건 무슨 뜻인가요?" / "여호와가 '목자'와 '주권자' 두 호칭을 함께 쓴 이유는?" / "장로들과 '언약'을 맺은 건 어떤 절차였나요?" / "왜 헤브론에서만 칠 년 반을 다스렸나요?" / "다윗이 기름 부음을 받은 게 이번이 몇 번째인가요?"
- 판단법: 질문을 보고 "본문의 **어느 단어·구절**에서 나온 건지" 짚을 수 있어야 한다. 못 짚으면 두루뭉술한 것이니 버려라.

## 카테고리는 '가이드'일 뿐
아래 공유 규칙의 카테고리 목록은 다양한 각도를 떠올리게 하는 가이드다. 그날 KB·본문이 뒷받침하지 않는 각도(어원 자료 없는 날의 원어 등)는 억지로 만들지 말고, 본문에서 직접 확인되는 관찰·디테일·인물·연결로 대체한다. 없는 원어 뜻·현대 지명·역사 추정으로 질문을 지어내지 않는다.

## 겹치면 안 되는 3가지 (이 질문들이 최종에서 탈락하는 기준)
독자는 이 질문 앞에서 이미 ⓐ오늘 본문 구절 ⓑ5단 묵상을 읽었다. 아래와 겹치면 알맹이가 없다:
1. **지난 질문** — `같은_책_기존_STEP2_질문`과 소재·맥락이 겹치면 문장이 달라도 안 된다.
2. **오늘 다른 질문** — 18개끼리 같은 소재 반복 금지. 특히 **한 메인의 두 꼬리가 같은 걸 묻거나, 꼬리의 답이 그 메인 답에 이미 들어갈 내용이면** 안 된다.
3. **이미 읽은 본문·5단** — 답이 오늘 본문 구절에 그대로 적혀 있거나(예: "다윗 나이 30세" — 5:4에 그대로), 5단이 이미 밝힌 사건·동기를 되묻는 것 금지.

## 메인↔꼬리 자가진단 (매우 중요)
꼬리는 메인을 '더 깊이 되풀이'하는 게 아니라 메인과 **다른 지점(다른 단서)**을 짚는다. 만들기 전 물어라 — "이 꼬리의 답이 메인 답 안에 이미 들어가나?" 그렇다면 버리고 다른 인물·사물·장소·연결로 각도를 바꾼다.
- ✗ 메인 "'헬갓 핫수림' 유래?" + 꼬리 "이 전투에서 '헬갓 핫수림'이라 불린 이유?" (유래=불린 이유)
- ✗ 메인 "이스보셋 이름의 의미?" + 꼬리 "이스보셋이 '수치의 사람'이란 이름을 가진 이유?" (메인 답이 뜻·이유 다 설명)
- ✗ 메인 "레갑·바아나가 죽인 방식은 어떤 의미?" + 꼬리 "적 머리를 가져온 게 승리를 상징한 이유?" (메인 답에 포함)

## '왜/이유' 단어는 금지가 아니다
5단이 안 다룬 주변 배경을 여는 '왜'는 오히려 알맹이다(브에롯 왜 이주, 헬갓핫수림 유래, 적 머리 관습). 막는 건 '이미 읽은 걸 되묻기'이지 '왜'라는 단어가 아니다.

## 출력
`{"mains": [ {"question","category","topic","follow_ups":[{"question","category","topic"}×2]} ×6 ]}`
- `question` 눌러보고 싶은 짧은 제목형 한 문장 · `category` 각도 라벨 · `topic` 1~4단어 소재 라벨"""

_JUDGE_WRAPPER = """# 떠오르는 질문 — 알맹이/재진술 판정기

각 후보 질문이 '독자에게 새로운가'를 판정한다. 독자는 이 질문 앞에서 이미 ①오늘 본문 구절(`본문_내용`) ②5단 묵상(`이미_다룬_5단`, 본문 따라가기)을 읽었다. 답변을 상상해서, 그 답이 이미 어딘가에 있으면 알맹이가 없다.

각 질문마다 `verdict`를 정확히 하나로:
- **좋음** — 답이 본문 구절·5단·(꼬리면) 같은 가지 메인 어디에도 그대로 없고, 새 각도(어원·배경·인물·지명·연결·문화)를 연다.
- **본문재진술** — 답이 오늘 `본문_내용` 절에 이미 그대로 적혀 있다. 예: "다윗이 왕위에 오른 나이는?" → 5:4에 '삼십 세에 왕위에 올라'가 그대로 있음.
- **5단재진술** — 답이 `이미_다룬_5단`이 이미 밝힌 사건·동기의 되풀이다.
- **메인에포함** — (그 질문이 '꼬리'일 때만) 답이 `이_꼬리의_메인_질문`의 답 안에 이미 들어갈 내용이다. 예: 메인 "죽인 방식의 의미?"의 답에 "적 머리=승리"가 이미 들어가는데 꼬리가 그걸 또 물음.
- **얕음** — 재진술은 아니지만, 답을 알아도 본문 이해가 안 바뀌는 트리비아.

의심스러우면 '좋음'을 기본으로 주지 말고, 정말 답이 이미 있는지 본문·5단 문장과 대조해라. 너는 판정만 한다 — 고쳐 쓰지 않는다.

## 두 번째 임무 — '답이 겹치는 지식 묶음' 그룹핑 (매우 중요)
질문 문장이나 카테고리가 달라도 **답을 쓰면 사실상 같은 지식·맥락을 설명하게 되는 질문들**이 있다. 독자는 묶음당 1개만 있으면 그 지식을 얻는다 — 나머지는 같은 걸 반복하는 것이다.

**반드시 이 순서로 판단해라:**
1. 각 질문마다 먼저 `answer_gist`에 **"이 질문에 답하면 결국 무슨 내용을 설명하게 되나"를 한 줄로** 적는다. (질문 표현이 아니라 '답의 알맹이'를 적어라)
2. 그다음 **answer_gist가 실질적으로 같거나 크게 겹치는 질문들**을 `answer_groups`로 묶는다.

**특히 조심할 패턴 — 같은 대상(숫자·인물·사건·장소)의 '의미/상징성/이유/배경/영향'을 각각 물으면 답이 같다:**
- "다윗이 30세에 오른 것의 **의미**?" / "30세가 성경에서 갖는 **상징성**?" → **같은 묶음** (둘 다 답이 '30세=성숙·준비된 지도자')
- "레갑·바아나의 문화적 배경?" / "그들의 동기?" / "그들의 행동에 대한 반응?" → **한 묶음**
- "다윗 통치의 신학적 의미?" / "다윗 왕권의 정당성?" → 한 묶음
- "백성들의 반응?" / "이스라엘 통합에 미친 영향?" → 한 묶음

반대로 "이스보셋 이름의 뜻?"(어원) / "브에롯은 어떤 곳?"(지명)은 gist가 달라 **서로 다른 묶음**이다.

의심스러우면 두 질문의 `answer_gist`를 나란히 놓고 "이 두 답을 각각 쓰면 독자가 서로 다른 걸 배우나, 같은 걸 두 번 배우나"를 물어라. 같은 걸 배우면 한 묶음이다.

## 출력
`{"evaluations": [{"id":"...", "answer_gist":"답 핵심 한 줄", "verdict":"...", "note":"..."}], "answer_groups": [["id1","id3"], ...]}`
— evaluations는 모든 후보(answer_gist 먼저), answer_groups는 gist가 겹치는 묶음만(2개 이상)."""

_QFIX_WRAPPER = """# 떠오르는 질문 — 질문 부분 교체기 (질문만)

이미 고른 9개 중 **문제가 있는 슬롯의 질문만** 새로 갈아끼운다. **답변은 만들지 않는다.**

입력: `고쳐야_할_슬롯`(각 role_id의 기존 질문+문제), `피해야_할_질문`(나머지 슬롯+과거 질문 전체).

규칙: 아래 공유 톤·질문 규칙을 따른다. 제목형 한 문장. 요청받은 role_id 전부 채운다.
- 교체 질문은 `피해야_할_질문`과 **답변 내용이 겹치면 안 된다** — 소재·표현만이 아니라 '답을 썼을 때 같은 지식이 나오는가'를 본다. **완전히 다른 각도·카테고리**(어원·지명·인물과거·시대배경·타 성경 연결)의 새 지식을 연다.
- `이미_다룬_5단`이 밝힌 사건·동기, 그리고 **오늘 본문 구절에 답이 그대로 있는 것**(나이·숫자 나열 등)을 되묻지 마라.
- 꼬리를 새로 쓸 땐 그 답이 같은 가지 메인 답에 이미 들어갈 내용이면 안 된다.

출력: `{"fixes": [{"role_id":"...","question":"..."}, ...]}`"""


def _shared(*names):
    return "\n\n---\n\n".join(fp._read(PARTS_DIR / n) for n in names)


def _q_system():
    return "\n\n---\n\n".join([_Q_WRAPPER, _shared("01_role_tone.md", "03_question_rules.md")])


def _qfix_system():
    return "\n\n---\n\n".join([_QFIX_WRAPPER, _shared("01_role_tone.md", "03_question_rules.md")])


def _judge_system():
    return _JUDGE_WRAPPER


# ===== 스키마 =====
def _q_leaf():
    return ({"question": {"type": "string"}, "category": {"type": "string"}, "topic": {"type": "string"}},
            ["question", "category", "topic"])


def _q_gen_schema(n_mains):
    lp, lr = _q_leaf()
    main_props = {"question": {"type": "string"}, "category": {"type": "string"}, "topic": {"type": "string"},
                  "follow_ups": {"type": "array", "minItems": 2, "maxItems": 2,
                                 "items": {"type": "object", "properties": lp, "required": lr,
                                           "additionalProperties": False}}}
    return {"type": "object", "properties": {
                "mains": {"type": "array", "minItems": n_mains, "maxItems": n_mains,
                          "items": {"type": "object", "properties": main_props,
                                    "required": ["question", "category", "topic", "follow_ups"],
                                    "additionalProperties": False}}},
            "required": ["mains"], "additionalProperties": False}


def _judge_schema():
    return {"type": "object", "properties": {
                "evaluations": {"type": "array", "items": {"type": "object",
                    "properties": {"id": {"type": "string"},
                                   "answer_gist": {"type": "string"},
                                   "verdict": {"type": "string", "enum": _JUDGE_VERDICTS},
                                   "note": {"type": "string"}},
                    "required": ["id", "answer_gist", "verdict", "note"], "additionalProperties": False}},
                "answer_groups": {"type": "array",
                    "items": {"type": "array", "items": {"type": "string"}}}},
            "required": ["evaluations", "answer_groups"], "additionalProperties": False}


def _qfix_schema(role_ids):
    return {"type": "object", "properties": {
                "fixes": {"type": "array", "items": {"type": "object",
                    "properties": {"role_id": {"type": "string", "enum": role_ids},
                                   "question": {"type": "string"}},
                    "required": ["role_id", "question"], "additionalProperties": False}}},
            "required": ["fixes"], "additionalProperties": False}


# ===== 중복 판정 헬퍼 (코드) =====
_SAME_DAY_LCS = 0.40


def _dup_same_day(q, topic, pq, pt):
    if fp._overlap(q, pq) or (topic and pt and fp._overlap(topic, pt)):
        return True
    if fp._lcs_ratio_max(q, pq) >= _SAME_DAY_LCS:
        return True
    if topic and pt and fp._norm(topic) == fp._norm(pt):
        return True
    return False


def _hist_dup(q, topic, history):
    for h in history:
        hq = h.get("question", "")
        if fp._same_context(q, hq) or (topic and fp._same_context(topic, hq)):
            return h.get("date", "")
    return None


# ===== ① 후보 생성 (mini) =====
def _gen_candidates(chat, qt, kb, deep5, history, total_cost, log=None):
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "오륜_질문": qt.get("oryun_questions", []), "지식": kb,
               "같은_책_기존_STEP2_질문": history, "이미_다룬_5단": deep5}
    # 응답이 max_tokens에 잘려 JSON이 깨지는 일이 있어(18개 생성) 재시도한다.
    last_err = None
    for attempt in range(3):
        try:
            data, cost = chat(Q_MODEL, _q_system(), payload, "followup_candidates",
                              _q_gen_schema(NUM_CANDIDATE_MAINS), 0.75, 8000)
            fp._add_cost(total_cost, cost)
            mains = data.get("mains") or []
            if mains:
                return [{"idx": i, "main": m, "tails": (m.get("follow_ups") or [])[:2]}
                        for i, m in enumerate(mains)]
        except Exception as e:
            last_err = e
            if log:
                log(f"  [simple] 후보 생성 시도 {attempt + 1} 실패(재시도): {e}", "WARN")
    raise fp.FollowUpPoolError(f"후보 생성 3회 실패: {last_err}")


def _branch_qs(b):
    return [(b["main"].get("question", ""), b["main"].get("topic", ""))] + \
           [(t.get("question", ""), t.get("topic", "")) for t in b["tails"]]


def _judge_ids(idx):
    return [f"b{idx}_m", f"b{idx}_t0", f"b{idx}_t1"]


# ===== ② 판정 (mini): 체3 본문·5단 재진술 + 체2 메인포함 =====
def _judge(chat, qt, deep5, branches, total_cost, log=None):
    cand = []
    for b in branches:
        i = b["idx"]
        cand.append({"id": f"b{i}_m", "종류": "메인", "question": b["main"].get("question", "")})
        for j, t in enumerate(b["tails"]):
            cand.append({"id": f"b{i}_t{j}", "종류": "꼬리",
                         "이_꼬리의_메인_질문": b["main"].get("question", ""),
                         "question": t.get("question", "")})
    payload = {"본문_내용": fp._body_text(qt), "이미_다룬_5단": deep5, "후보_질문": cand}
    try:
        data, cost = chat(JUDGE_MODEL, _judge_system(), payload, "followup_judge",
                          _judge_schema(), 0.1, 5000)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [simple] 판정 호출 실패 — 전부 '좋음' 취급: {e}", "WARN")
        return {}, {}
    verdicts = {e.get("id"): e.get("verdict", _GOOD) for e in data.get("evaluations", [])}
    # 답 겹치는 묶음 → id별 클러스터 라벨(묶이지 않은 건 자기 id가 클러스터=고유)
    clusters = {}
    for gi, group in enumerate(data.get("answer_groups", [])):
        for cid in group:
            clusters[cid] = f"g{gi}"
    return verdicts, clusters


# ===== ③ 다양성 조합 선택 (묶음 해체 → 카테고리 다양하게 → 느슨한 짝짓기) =====
# 8개 STEP2 카테고리로 정규화(다양성 계산용). mini가 라벨을 다양하게 붙여도 같은 뜻끼리 묶는다.
_CANON = {"주석": "주석/본문관찰", "본문관찰": "주석/본문관찰", "지명": "지명", "지리": "지명",
          "어원": "어원·유래", "인물": "인물 배경", "문화": "문화·관습", "신학": "신학/해석",
          "본문 디": "본문 디테일", "본문디": "본문 디테일", "디테일": "본문 디테일",
          "연결": "연결", "랜덤": "랜덤"}


def _canon_cat(c):
    c = (c or "").strip()
    for k, v in _CANON.items():
        if c.startswith(k):
            return v
    return c or "기타"


def _shared_chunk(a, b, minlen=3):
    """두 문장이 공유하는 가장 긴 연속 글자덩어리 길이(정규화 후). 같은 인물·지명(브에롯,
    이스보셋, 헤브론 등)을 공유하는지 잡는다."""
    na, nb = fp._norm(a), fp._norm(b)
    if not na or not nb:
        return 0
    for L in range(min(len(na), 8), minlen - 1, -1):
        for i in range(len(na) - L + 1):
            if na[i:i + L] in nb:
                return L
    return 0


def _relatedness(a, b):
    """메인-꼬리 연관성(0~1). 같은 소재=1, 같은 인물·지명 공유=0.5~0.7, 아니면 문장 LCS."""
    ta, tb = a.get("topic", ""), b.get("topic", "")
    if ta and tb and fp._norm(ta) == fp._norm(tb):
        return 1.0
    if fp._overlap(ta, tb):
        return 0.85
    lcs = fp._lcs_ratio_max(a.get("q", ""), b.get("q", ""))
    chunk = _shared_chunk(a.get("q", ""), b.get("q", ""))  # 공유 고유명사 길이
    if chunk >= 5:
        return max(0.7, lcs)
    if chunk >= 3:
        return max(0.5, lcs)
    return lcs


def _dedup_pool(pool):
    kept = []
    for c in pool:
        if any(_dup_same_day(c["q"], c["topic"], k["q"], k["topic"]) for k in kept):
            continue
        kept.append(c)
    return kept


def _pick_diverse(pool, n, *, used_clusters=None, prefer_main=False, avoid_cats=()):
    """서로 다른 '답 지식 묶음(cluster)'을 우선 피하면서(=답 겹침 방지), 그다음 카테고리도
    다양하게 n개를 고른다. cluster가 최우선 — 답이 겹치는 질문을 여러 개 안 뽑는다."""
    used_clusters = set(used_clusters or [])
    picked, cats = [], Counter()
    remaining = list(pool)
    while len(picked) < n and remaining:
        elig = [c for c in remaining if c["cluster"] not in used_clusters
                and not any(_dup_same_day(c["q"], c["topic"], p["q"], p["topic"]) for p in picked)]
        if not elig:  # 서로 다른 묶음이 동날 때만 같은 묶음 허용(재료 부족 — 지어내기 안 함)
            elig = [c for c in remaining
                    if not any(_dup_same_day(c["q"], c["topic"], p["q"], p["topic"]) for p in picked)]
            if not elig:
                break
        c = min(elig, key=lambda c: (cats[c["cat"]], c["cat"] in avoid_cats,
                                     0 if (prefer_main and c["was_main"]) else 1))
        picked.append(c)
        cats[c["cat"]] += 1
        used_clusters.add(c["cluster"])
        remaining.remove(c)
    return picked


def _flatten_pool(branches, verdicts, clusters):
    pool = []
    for b in branches:
        i = b["idx"]
        mid = f"b{i}_m"
        pool.append({"q": b["main"].get("question", ""), "cat": _canon_cat(b["main"].get("category", "")),
                     "topic": b["main"].get("topic", ""), "verdict": verdicts.get(mid, _GOOD),
                     "cluster": clusters.get(mid, mid), "was_main": True, "sel": False})
        for j, t in enumerate(b["tails"]):
            tid = f"b{i}_t{j}"
            pool.append({"q": t.get("question", ""), "cat": _canon_cat(t.get("category", "")),
                         "topic": t.get("topic", ""), "verdict": verdicts.get(tid, _GOOD),
                         "cluster": clusters.get(tid, tid), "was_main": False, "sel": False})
    return pool


# ===== 코드 하드게이트: '같은 대상의 의미↔영향'은 답이 겹친다 → 결정적으로 한 묶음 =====
# mini가 놓쳐도 코드가 못박는다. 사장님이 반복 지적한 겹침이 거의 이 형태였다.
_MEANING_RE = re.compile(r"의미|의의|뜻|이유|까닭|왜|상징|목적|중요")
_EFFECT_RE = re.compile(r"영향|변화|효과|결과|기여|미친|미쳤|달라")
# 소재(대상)로 안 쳐줄 흔한 말 — 이게 겹친다고 같은 대상은 아니다.
_SUBJ_STOP = {"다윗", "이스라엘", "하나님", "여호와", "사람", "백성", "우리", "당신", "무엇", "어떤",
              "어떻게", "누구", "이유", "의미", "의의", "영향", "변화", "효과", "결과", "목적", "중요",
              "관계", "상황", "과정", "때문", "역할", "모습", "방식",
              # 흔한 '프레이밍' 단어 — 이게 겹친다고 같은 대상이 아니다(오탐 방지)
              "통치", "왕위", "왕권", "즉위", "등극", "시대", "나라", "왕국", "지도자", "사건", "역사",
              "대해", "관해", "위해", "통해", "대한"}
_TOK_RE = re.compile(r"[가-힣]{2,}")
_JOSA_RE = re.compile(r"(은|는|이|가|을|를|의|에게|에서|에|과|와|도|으로|로|만|께서|께)$")


def _subject_tokens(*texts):
    out = set()
    for t in texts:
        for w in _TOK_RE.findall(t or ""):
            w = _JOSA_RE.sub("", w)
            if len(w) >= 2 and w not in _SUBJ_STOP:
                out.add(w)
    return out


def _meaning_effect_pair(a, b):
    """같은 대상 + 하나는 의미/이유형·다른 하나는 영향/변화형이면 답이 겹친다.
    어원·지명은 '뜻·위치'라는 사실 조회라 의미↔영향 겹침 대상이 아니므로 제외."""
    if a["cat"] in ("어원·유래", "지명") or b["cat"] in ("어원·유래", "지명"):
        return False
    if not (_subject_tokens(a["q"], a["topic"]) & _subject_tokens(b["q"], b["topic"])):
        return False
    am, ae = bool(_MEANING_RE.search(a["q"])), bool(_EFFECT_RE.search(a["q"]))
    bm, be = bool(_MEANING_RE.search(b["q"])), bool(_EFFECT_RE.search(b["q"]))
    return (am and be) or (ae and bm)


def _gate_clusters(pool, log=None):
    """union-find로 (mini 클러스터) + (의미↔영향 코드 게이트)를 합쳐 최종 지식묶음을 만든다."""
    n = len(pool)
    parent = list(range(n))

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    def union(i, j):
        parent[find(i)] = find(j)

    seen = {}
    for i, c in enumerate(pool):  # 먼저 mini가 준 클러스터끼리 union
        if c["cluster"] in seen:
            union(i, seen[c["cluster"]])
        else:
            seen[c["cluster"]] = i
    for i in range(n):            # 그다음 의미↔영향 게이트로 추가 union
        for j in range(i + 1, n):
            if find(i) != find(j) and _meaning_effect_pair(pool[i], pool[j]):
                if log:
                    log(f"  [simple] 의미↔영향 게이트 병합: '{pool[i]['q'][:16]}…' ≡ '{pool[j]['q'][:16]}…'", "INFO")
                union(i, j)
    for i, c in enumerate(pool):
        c["cluster"] = f"c{find(i)}"
    return pool


def _assemble_diverse(pool, history, log=None):
    """묶음 해체 → 답 겹침(cluster) 안 되게 + 카테고리 다양하게 메인3·꼬리6 선택 → 느슨히 짝짓기."""
    clean = _dedup_pool([c for c in pool if c["verdict"] == _GOOD and not _hist_dup(c["q"], c["topic"], history)])
    if len(clean) < 9:  # 깨끗한 게 모자라면 플래그된 것 중 덜 나쁜 걸 보충(드문 경우)
        extra = _dedup_pool([c for c in pool if c not in clean])
        clean = clean + extra[: 9 - len(clean)]

    mains = _pick_diverse(clean, 3, prefer_main=True)
    used_clusters = {m["cluster"] for m in mains}
    rest = [c for c in clean if c not in mains]
    tails = _pick_diverse(rest, 6, used_clusters=used_clusters, avoid_cats={m["cat"] for m in mains})
    if len(tails) < 6:
        tails += [c for c in rest if c not in tails][: 6 - len(tails)]

    # 느슨한 짝짓기: (꼬리,메인) 쌍을 연관성 높은 순으로 배치, 메인당 최대 2개
    pairs = sorted(((-_relatedness(t, mains[mi]), ti, mi) for ti, t in enumerate(tails) for mi in range(len(mains))))
    assign = [[] for _ in mains]
    done = set()
    for negrel, ti, mi in pairs:
        if ti in done or len(assign[mi]) >= 2:
            continue
        assign[mi].append(tails[ti])
        done.add(ti)

    tree, rid = [], iter(_ROLE_IDS)
    for mi, m in enumerate(mains):
        m["sel"] = True
        node = {"role_id": next(rid), "question": m["q"], "category": m["cat"],
                "topic": m["topic"], "follow_ups": []}
        for t in assign[mi]:
            t["sel"] = True
            node["follow_ups"].append({"role_id": next(rid), "question": t["q"],
                                       "category": t["cat"], "topic": t["topic"]})
        tree.append(node)
    picked_all = mains + [t for row in assign for t in row]
    if log:
        cov = sorted({n["category"] for n in fp._iter_all(tree)})
        nclust = len({c["cluster"] for c in picked_all})
        log(f"  [simple] 다양성 조합 → 카테고리 {len(cov)}개 {cov} · 서로 다른 지식묶음 {nclust}/9", "INFO")
    return tree


def _cand_dump(pool):
    """후보 18개 전체를 판정·선택여부·지식묶음과 함께 기록."""
    return [{"question": c["q"], "category": c["cat"], "topic": c["topic"], "verdict": c["verdict"],
             "cluster": c["cluster"], "was_main": c["was_main"], "selected": c["sel"]} for c in pool]


# ===== 최종 9개 잔여 문제 수집 (코드 체1·체2 + 판정 잔여) =====
def _residual_problems(tree, history, role_verdicts):
    problems = {}
    seen = []
    for node in fp._iter_all(tree):
        rid = node["role_id"]
        q = node.get("question", "")
        topic = node.get("topic") or q
        reasons = []
        d = _hist_dup(q, topic, history)
        if d:
            reasons.append(f"지난질문 중복({d})")
        if any(_dup_same_day(q, topic, pq, pt) for pq, pt in seen):
            reasons.append("당일 서로 중복")
        v = role_verdicts.get(rid, _GOOD)
        if v != _GOOD:
            reasons.append(v)
        if reasons:
            problems[rid] = "; ".join(reasons)
        seen.append((q, topic))
    return problems


# ===== 걸린 질문 교체 (mini) =====
def _qfix(chat, qt, kb, deep5, tree, problems, history, total_cost, log=None):
    nodes = {n["role_id"]: n for n in fp._iter_all(tree)}
    targets = [{"role_id": rid, "기존_질문": nodes[rid]["question"], "문제": r}
               for rid, r in problems.items() if rid in nodes]
    if not targets:
        return tree
    avoid = [n["question"] for n in fp._iter_all(tree) if n["role_id"] not in problems]
    avoid += [h.get("question", "") for h in history]
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "지식": kb, "이미_다룬_5단": deep5, "고쳐야_할_슬롯": targets, "피해야_할_질문": avoid}
    rids = [t["role_id"] for t in targets]
    try:
        data, cost = chat(QFIX_MODEL, _qfix_system(), payload, "followup_qfix",
                          _qfix_schema(rids), 0.7, 2000)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [simple] 질문 교체 실패 — 원본 유지: {e}", "WARN")
        return tree
    for item in data.get("fixes", []):
        rid = item.get("role_id")
        if rid in nodes and item.get("question"):
            if log:
                log(f"  [simple] 교체 {rid}: '{nodes[rid]['question'][:16]}…' → '{item['question'][:16]}…'", "INFO")
            nodes[rid]["question"] = item["question"]
    return tree


def _usable_kb(kb):
    if not kb:
        return None
    return kb if any(isinstance(k, str) and k.isdigit() for k in kb.keys()) else None


# ===== 오케스트레이션 =====
def run_simple(chat, qt, kb, deep5, *, history=None, mode="none", log=None):
    history = history or []
    total_cost = dict(_ZERO_COST)
    kb_use = _usable_kb(kb)

    # ① 후보 18개 생성
    branches = _gen_candidates(chat, qt, kb_use, deep5, history, total_cost, log=log)
    calls = 1
    # ② 판정 (본문·5단 재진술 + 메인포함) + 답 겹치는 지식묶음 그룹핑
    verdicts, clusters = _judge(chat, qt, deep5, branches, total_cost, log=log)
    calls += 1
    if log:
        vc = Counter(verdicts.values())
        log(f"  [simple/{mode}] 후보 18개 판정: {dict(vc)} · 답겹침 묶음 {len(set(clusters.values()))}개", "INFO")
    # ③ 묶음 해체 → 답 겹침 + 카테고리 다양하게 메인3·꼬리6 선택 → 느슨한 짝짓기
    pool = _flatten_pool(branches, verdicts, clusters)
    pool = _gate_clusters(pool, log=log)  # 의미↔영향 코드 하드게이트로 지식묶음 확정
    tree = _assemble_diverse(pool, history, log=log)
    role_v = {c["q"]: c["verdict"] for c in pool}  # 질문문→판정 (잔여 검사용)

    # 선택된 9개의 잔여 문제(체1 지난질문 + 체2 표면 + 판정 잔여)만 교체
    problems = _residual_problems(tree, history, {n["role_id"]: role_v.get(n["question"], _GOOD)
                                                  for n in fp._iter_all(tree)})
    initial_problems = dict(problems)
    if log and problems:
        log(f"  [simple/{mode}] 선택 9개 잔여 문제 {len(problems)}건 → 교체: "
            + "; ".join(f"{r}({v[:20]})" for r, v in problems.items()), "WARN")
    fix_rounds = 0
    while problems and fix_rounds < 2:
        tree = _qfix(chat, qt, kb_use, deep5, tree, problems, history, total_cost, log=log)
        calls += 1
        fix_rounds += 1
        problems = _residual_problems(tree, history, {})  # 교체 후엔 코드 체1·2만 재검(판정 재호출 안 함)
    residual = problems
    if residual and log:
        log(f"  [simple/{mode}] 최종 미해결 {len(residual)}건(원본 유지): {list(residual)}", "ERR")

    # ④ 답변 1회 (4o, 검증+재시도)
    answers = fp.write_answers(chat, qt, kb_use, deep5, tree, total_cost)
    fp._apply_answers(tree, answers)
    calls += 1

    items = [{"question": m["question"], "answer": m["answer"],
              "follow_ups": [{"question": t["question"], "answer": t["answer"]} for t in m["follow_ups"]]}
             for m in tree]
    covered = sorted({n["category"] for n in fp._iter_all(tree)})
    sel_clusters = [c["cluster"] for c in pool if c["sel"]]
    meta = {
        "generation_method": f"simple5_distinct_{mode}",
        "gpt_calls": calls, "fix_rounds": fix_rounds,
        "candidate_count": sum(1 + len(b["tails"]) for b in branches),
        "judge_verdicts": dict(Counter(verdicts.values())),
        "answer_group_count": len(set(clusters.values())),
        "distinct_knowledge_in_final": len(set(sel_clusters)),
        "covered_categories": covered,
        "candidates": _cand_dump(pool),
        "kb_coverage": fp.count_kb_coverage(kb),
        "initial_problems": initial_problems, "residual_unresolved": list(residual),
        "category_map": [{"role_id": m["role_id"], "category": m.get("category"),
                          "topic": m.get("topic"), "question": m["question"]}
                         for m in fp._iter_all(tree)],
    }
    return items, total_cost, meta
