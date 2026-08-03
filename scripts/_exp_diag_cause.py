# -*- coding: utf-8 -*-
"""중복의 원인 규명 — 관문 통과 '전' 데이터(옛 엔진 88일)에서 진짜 겹침 쌍만 모아 분석.
새 생성 없음. 임베딩은 _embed_cache.json 캐시만 사용(API 호출 0).

핵심 가설 검증:
  H1. 질문 생성 로직이 비슷한 질문을 만든다  → 질문 유사도도 높아야 함
  H2. 질문은 다른데 답변이 같은 곳으로 수렴한다 → 질문 유사도는 낮고 답변만 높음
"""
import sys, json, itertools
from pathlib import Path
from collections import Counter

EXP = Path(__file__).resolve().parent.parent   # repo 루트 (이 파일은 repo/scripts/ 안)
sys.path.insert(0, str(EXP / "scripts"))
import _measure_answer_overlap as mao

TH = mao.SIM_THRESHOLD
CACHE = json.load(open(EXP / "scripts" / "_embed_cache.json", encoding="utf-8"))


def cached(texts):
    """캐시에 있는 것만. 하나라도 없으면 None(그 날은 건너뜀) → API 호출 0."""
    if any(mao._key(t) not in CACHE for t in texts):
        return None
    return [CACHE[mao._key(t)] for t in texts]


def flat(j):
    meta = j.get("_followup_meta") or {}
    cm = {c["question"]: c for c in (meta.get("candidates") or [])}
    catm = {c.get("question"): c.get("category") for c in (meta.get("category_map") or [])}
    out = []
    for m in j.get("follow_up_questions") or []:
        for q in [m] + list(m.get("follow_ups") or []):
            c = cm.get(q["question"], {})
            out.append({"q": q["question"], "a": q.get("answer", ""),
                        "verse": c.get("verse"), "cluster": c.get("cluster"),
                        "cat": c.get("category") or catm.get(q["question"]),
                        "gist": c.get("gist", "")})
    return out


pairs = []
days_scanned = days_with_dup = 0
for p in sorted((EXP / "data" / "deep_dive").glob("2026-0*.json")):
    j = json.load(open(p, encoding="utf-8"))
    ns = flat(j)
    if len(ns) < 2 or not all(n["a"] and n["q"] for n in ns):
        continue
    av, qv = cached([n["a"] for n in ns]), cached([n["q"] for n in ns])
    if av is None or qv is None:
        continue
    days_scanned += 1
    hit = False
    for i, k in itertools.combinations(range(len(ns)), 2):
        sa = mao.cosine(av[i], av[k])
        if sa >= TH:
            hit = True
            pairs.append({"date": p.stem, "ref": j.get("scripture_ref", ""),
                          "sa": sa, "sq": mao.cosine(qv[i], qv[k]),
                          "A": ns[i], "B": ns[k]})
    days_with_dup += hit

print(f"검사 {days_scanned}일 · 겹침 있는 날 {days_with_dup}일 · 겹침 쌍 총 {len(pairs)}건 (API 호출 0)\n")

# H1 vs H2
lo_q = [x for x in pairs if x["sq"] < 0.60]
mid_q = [x for x in pairs if 0.60 <= x["sq"] < 0.75]
hi_q = [x for x in pairs if x["sq"] >= 0.75]
print("[H1 vs H2] 겹친 쌍의 '질문끼리' 유사도 분포")
print(f"  질문 낮음(<0.60)  : {len(lo_q):3}건 ({len(lo_q)/len(pairs)*100:.0f}%)  ← 질문은 딴판인데 답만 수렴 = H2")
print(f"  질문 중간(.60~.75): {len(mid_q):3}건 ({len(mid_q)/len(pairs)*100:.0f}%)")
print(f"  질문 높음(≥0.75)  : {len(hi_q):3}건 ({len(hi_q)/len(pairs)*100:.0f}%)  ← 질문부터 닮음 = H1")
sq_avg = sum(x["sq"] for x in pairs) / len(pairs)
sa_avg = sum(x["sa"] for x in pairs) / len(pairs)
print(f"  평균: 답변 {sa_avg:.3f} vs 질문 {sq_avg:.3f}  (차이 {sa_avg-sq_avg:+.3f})")

print("\n[자리·묶음] 겹친 쌍은 어디서 나오나")
c = Counter()
for x in pairs:
    c["같은 절" if x["A"]["verse"] == x["B"]["verse"] and x["A"]["verse"] is not None else "다른 절"] += 1
    c["같은 묶음" if x["A"]["cluster"] == x["B"]["cluster"] and x["A"]["cluster"] is not None else "다른 묶음"] += 1
for k, v in c.most_common():
    print(f"  {k}: {v}건 ({v/len(pairs)*100:.0f}%)")

print("\n[카테고리] 겹친 쌍의 각도 조합 상위")
cc = Counter(tuple(sorted([str(x["A"]["cat"]), str(x["B"]["cat"])])) for x in pairs)
for (a, b), v in cc.most_common(6):
    print(f"  {a} ↔ {b}: {v}건")

print("\n[가장 심한 쌍 8건] — 질문은 얼마나 다른지 같이 보기")
for x in sorted(pairs, key=lambda x: -x["sa"])[:8]:
    print(f"\n  {x['date']} {x['ref']} · 답 {x['sa']:.3f} / 질문 {x['sq']:.3f}")
    print(f"     A({x['A']['cat']}, {x['A']['verse']}절): {x['A']['q']}")
    print(f"     B({x['B']['cat']}, {x['B']['verse']}절): {x['B']['q']}")

json.dump([{k: (v if k not in ("A", "B") else {kk: vv for kk, vv in v.items() if kk != "a"})
            for k, v in x.items()} for x in pairs],
          open(Path(__file__).parent / "dup_pairs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n(쌍 목록 저장: dup_pairs.json)")
