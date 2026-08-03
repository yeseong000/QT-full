# -*- coding: utf-8 -*-
"""카테고리별 예시 작성판 — 사장님이 직접 채우실 문서를 만든다.

카테고리마다 다음을 한자리에 모은다:
  ① 이 카테고리가 '먹는 재료'가 KB의 무엇인지 (key_details.cat ↔ 질문 카테고리)
  ② 그 재료의 실제 재고 (장별 개수 · 평균) — 상한을 재고에 연동하려면 이 숫자가 근거
  ③ 재료 실물 예시 — 사장님이 예시를 쓰실 때 "무엇을 갖고 묻는가"를 보시라고
  ④ 실제로 안 겹친 질문 / 겹쳐서 잘린 질문
  ⑤ ✍️ 사장님이 채우실 칸

새 생성 없음 · 임베딩은 캐시만(API 0).
사용: python scripts/_exp_cat_worksheet.py [출력경로.md]
"""
import sys, json, itertools
from pathlib import Path
from collections import defaultdict, Counter

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "scripts"))
import followup_simple as fs
import _measure_answer_overlap as mao

CACHE_P = EXP / "scripts" / "_embed_cache.json"
CACHE = json.load(open(CACHE_P, encoding="utf-8")) if CACHE_P.exists() else {}
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else EXP.parent / "카테고리_예시_작성판.md"

# 질문 카테고리 → (먹는 key_details.cat, 추가로 쓸 수 있는 장 차원 필드, 프롬프트 '질문 각도' 번호)
SPEC = {
    "주석형/본문관찰": ("본문관찰", [], None),
    "본문 디테일":     ("본문관찰", [], "2. 놓치기 쉬운 디테일"),
    "지명 정보":       ("지리",     [], "4. 지명"),
    "어원·유래":       ("어원",     [], "1. 단어의 원어·어원"),
    "인물 배경":       ("인물배경", ["인물"], "3. 인물의 과거·정체"),
    "문화·관습":       ("문화관습", [], "5. 문화·관습"),
    "신학/해석 견해":  ("신학핵심", ["주의점", "신학_핵심"], "6. 해석이 갈리는 대목"),
    "연결 질문":       (None,       [], "7. 연결 (관주_연결에서)"),
    "랜덤":           (None,       [], None),
}
ORDER = list(SPEC)


def cached(ts):
    if any(mao._key(t) not in CACHE for t in ts):
        return None
    return [CACHE[mao._key(t)] for t in ts]


# ===== ① KB 재고 조사 =====
stock = defaultdict(dict)      # cat -> {장: 개수}
extra_stock = defaultdict(dict)  # 필드 -> {장: 개수}
samples = defaultdict(list)    # cat -> [(장, verse, fact)]
books = []
for p in sorted((EXP / "data" / "reference").glob("*.json")):
    if p.name.endswith(".bak"):
        continue
    kb = json.load(open(p, encoding="utf-8"))
    if not isinstance(kb, dict):
        continue
    books.append(p.stem)
    for ck, ch in kb.items():
        if not ck.isdigit() or not isinstance(ch, dict):
            continue
        tag = f"{p.stem} {ck}"
        for d in ch.get("key_details") or []:
            c = d.get("cat")
            stock[c][tag] = stock[c].get(tag, 0) + 1
            if len(samples[c]) < 3:
                samples[c].append((tag, d.get("verse"), d.get("fact")))
        for f in ("인물", "주의점", "신학_핵심"):
            v = ch.get(f)
            n = len(v) if isinstance(v, list) else (1 if v else 0)
            if n:
                extra_stock[f][tag] = n

# ===== ② 실제 사용·겹침 =====
use, inv = Counter(), Counter()
clean, dirty = defaultdict(list), defaultdict(list)
for p in sorted((EXP / "data" / "deep_dive").glob("2026-0*.json")):
    j = json.load(open(p, encoding="utf-8"))
    meta = j.get("_followup_meta") or {}
    cm = {c["question"]: c for c in (meta.get("candidates") or [])}
    catm = {c.get("question"): c.get("category") for c in (meta.get("category_map") or [])}
    ns = []
    for it in j.get("follow_up_questions") or []:
        for q in [it] + list(it.get("follow_ups") or []):
            c = cm.get(q["question"], {})
            ns.append({"q": q["question"], "a": q.get("answer", ""),
                       "cat": fs._canon_cat(c.get("category") or catm.get(q["question"]) or "")})
    if len(ns) < 2 or not all(x["a"] for x in ns):
        continue
    v = cached([x["a"] for x in ns])
    bad = set()
    if v:
        for i, k in itertools.combinations(range(len(ns)), 2):
            if mao.cosine(v[i], v[k]) >= 0.75:
                bad.add(i); bad.add(k)
    for i, x in enumerate(ns):
        use[x["cat"]] += 1
        if i in bad:
            inv[x["cat"]] += 1
            dirty[x["cat"]].append((p.stem, x["q"]))
        else:
            clean[x["cat"]].append((p.stem, x["q"]))


def avg_stock(qcat):
    kbcat, fields, _ = SPEC[qcat]
    if not kbcat:
        return None, {}
    per = stock.get(kbcat, {})
    return (sum(per.values()) / len(per) if per else 0), per


L = []
A = L.append
A("# 떠오르는 질문 — 카테고리별 예시 작성판\n")
A("> **사장님이 채우실 곳은 `✍️` 입니다.** 채워 주시면 `prompts/follow_up/parts/03_question_rules.md`에 반영합니다.\n")
A("## 왜 이 문서가 필요한가\n")
A("KB에는 사실마다 `cat` 라벨이 이미 붙어 있고, 그게 질문 카테고리와 **1:1로 맞습니다.**")
A("그런데 프롬프트는 이 연결을 한 번도 말해주지 않습니다 — 모델은 통짜 덩어리를 받아 자유연상합니다.")
A("그래서 `지리` 재료가 눈앞에 있는 날에도 \"~이 왕국에 어떤 영향을?\" 같은 추상 질문이 나옵니다.\n")
A("아래 표의 **재고**는 '그 카테고리가 하루에 정직하게 만들 수 있는 질문 수'의 상한선입니다.")
A("재고보다 많이 만들면 지어내고, 지어내면 답이 수렴해 겹칩니다.\n")

A("| 카테고리 | 먹는 재료 | 장당 평균 재고 | 지금 사용 | 겹침 연루 | 프롬프트 설명 |")
A("|---|---|---:|---:|---:|---|")
for c in ORDER:
    kbcat, fields, desc = SPEC[c]
    avg, per = avg_stock(c)
    src = f"`cat={kbcat}`" if kbcat else "—"
    if fields:
        src += " + " + "·".join(f"`{f}`" for f in fields)
    avgs = f"{avg:.1f}개" if avg is not None else "관주"
    u = use.get(c, 0)
    r = f"{inv.get(c,0)/u*100:.0f}%" if u else "—"
    A(f"| `{c}` | {src} | {avgs} | {u}회 | {r} | {desc or '**없음** ❌'} |")
A("")
A("> `연결 질문`은 KB가 아니라 **관주(`관주_연결`)**를 먹습니다. `랜덤`은 정의도 재료도 없습니다 — 없앨지 정해야 합니다.\n")
A("---\n")

for c in ORDER:
    kbcat, fields, desc = SPEC[c]
    avg, per = avg_stock(c)
    u, iv = use.get(c, 0), inv.get(c, 0)
    A(f"## `{c}`\n")
    A(f"**먹는 재료**: " + (f"`key_details.cat = {kbcat}`" if kbcat else "관주(`관주_연결`) — KB 아님")
      + (" + 장 차원 " + "·".join(f"`{f}`" for f in fields) if fields else ""))
    A(f"**프롬프트 설명**: {desc or '**없음 — 모델이 짐작하고 있습니다**'}")
    A(f"**실적**: {u}회 사용 · 겹침 연루 {iv}회"
      + (f" ({iv/u*100:.0f}%)" if u else "") + "\n")
    if kbcat and per:
        recent = sorted(per.items())[-6:]
        A(f"**재고** (장당 평균 {avg:.1f}개) — 최근 장:  "
          + " · ".join(f"{k} {v}개" for k, v in recent))
        if fields:
            for f in fields:
                fp_ = extra_stock.get(f, {})
                if fp_:
                    rec = sorted(fp_.items())[-4:]
                    A(f"  · 장 차원 `{f}`: " + " · ".join(f"{k} {v}개" for k, v in rec))
        A("")
    if samples.get(kbcat):
        A("**재료 실물** (모델이 이걸 갖고 묻습니다)\n")
        for tag, vs, fact in samples[kbcat]:
            A(f"- `{tag}` {vs} — {fact}")
        A("")
    ok, ng = clean.get(c, [])[:5], dirty.get(c, [])[:4]
    if ok:
        A("**실제로 안 겹친 질문**\n")
        for d, q in ok:
            A(f"- {q}  <sub>{d}</sub>")
        A("")
    if ng:
        A("**겹쳐서 잘린 질문**\n")
        for d, q in ng:
            A(f"- ✗ {q}  <sub>{d}</sub>")
        A("")
    A("✍️ **이 카테고리는 무엇을 묻는 자리인가** (한 문장):\n")
    A("> \n")
    A("✍️ **좋은 예 2~3개** — 위 '재료 실물'을 갖고 물었다면 어떻게 묻겠는가:\n")
    A("> - \n> - \n")
    A("✍️ **이건 이 카테고리가 아니다** (헷갈리는 반례 1~2개):\n")
    A("> - \n")
    A("---\n")

A("## 답변 단락 — 지금은 2단락으로 못박혀 있습니다\n")
A("1~3단락 가변으로 가려면 **세 군데**를 같이 풀어야 합니다:\n")
A("| 위치 | 지금 |")
A("|---|---|")
A("| `prompts/follow_up/parts/04_answer_rules.md` 6행 | \"**2단락 필수**\" |")
A("| `prompts/follow_up/parts/05_self_check.md` 18행 | \"각 답변 2단락 + `\\n\\n` 한 번\" |")
A("| `scripts/followup_pool.py` `_validate_answers` | **코드가 강제** — `\\n\\n`이 정확히 1번이 아니면 실패시키고 재시도 |")
A("")
A("세 번째가 핵심입니다. 프롬프트만 고치면 코드가 걷어내서 계속 2단락으로 돌아옵니다.\n")
A("✍️ **1단락으로 충분한 질문은 어떤 것인가**:\n> \n")
A("✍️ **3단락까지 가도 되는 질문은 어떤 것인가**:\n> \n")
A("✍️ **길이 제한(지금 프롬프트 300~450자 · 코드 180~600자)은 어떻게 할까요**:\n> \n")

OUT.write_text("\n".join(L), encoding="utf-8")
print(f"저장: {OUT}")
print(f"책 {len(books)}권 · KB cat {len(stock)}종 · 카테고리 {len(ORDER)}개")
for c in ORDER:
    avg, per = avg_stock(c)
    print(f"  {c:<16} 재고 평균 {avg if avg is not None else '-':>5} · 사용 {use.get(c,0):>3}회 · 연루 {inv.get(c,0):>2}회")
