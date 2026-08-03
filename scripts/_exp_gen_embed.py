# -*- coding: utf-8 -*-
"""객관적 잣대(답변 임베딩 겹침 ≥0.75)로 측정.
run_simple로 9개(답변 포함) 생성 → 임베딩 → 겹침 쌍 = 진짜 중복.
그다음 겹치는 건 빼고 distinct만 남긴 '정직한 가변 개수'도 같은 잣대로 확인.
사용: python gen_embed.py <date...>
"""
import sys, json
from pathlib import Path
from collections import defaultdict

EXP = Path(r"C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER\3146c29a-330a-4a5d-a385-72ab7951f69b\scratchpad\qt-exp")
OUT = Path(__file__).parent / "exp_out" / "embed"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(EXP / "scripts"))
import generate_meditation as gm
import followup_simple as fs
import _measure_answer_overlap as mao   # embed_all, cosine, SIM_THRESHOLD=0.75

TH = mao.SIM_THRESHOLD  # 0.75


def _silent(*a, **k):
    pass


def uf(pairs, n):
    p = list(range(n))
    def f(x):
        while p[x] != x: p[x] = p[p[x]]; x = p[x]
        return x
    for a, b in pairs:
        ra, rb = f(a), f(b)
        if ra != rb: p[rb] = ra
    g = defaultdict(list)
    for i in range(n): g[f(i)].append(i)
    return [sorted(v) for v in g.values()]


def run_day(date):
    qt = json.load(open(EXP / "data" / "qt" / f"{date}.json", encoding="utf-8"))
    dd = json.load(open(EXP / "data" / "deep_dive" / f"{date}.json", encoding="utf-8"))
    variants = dd.get("variants") or []
    deep5 = variants[0] if variants else {k: dd.get(k, "") for k in ["장면", "질문", "맥락", "통찰", "연결"]}
    kb = gm.slice_kb_to_passage(gm.load_kb(qt.get("book_name", "")), qt)
    history = gm.load_same_book_followup_history(qt)
    items, cost, meta = fs.run_simple(gm._fu_chat_v2, qt, kb, deep5, history=history, log=_silent)

    # 9개 평탄화 + 관주 표시(category_map의 '연결 질문')
    cat = {}
    for m in (meta.get("category_map") or []):
        cat[m.get("question")] = m.get("category")
    flat = []
    for m in items:
        for q in [m] + (m.get("follow_ups") or []):
            flat.append({"q": q.get("question", ""), "a": q.get("answer", ""),
                         "gwanju": cat.get(q.get("question")) == "연결 질문"})
    n = len(flat)
    answers = [f["a"] for f in flat]
    vecs = mao.embed_all(answers)
    # 겹침 쌍(≥0.75)
    flagged = []
    for i in range(n):
        for j in range(i + 1, n):
            s = mao.cosine(vecs[i], vecs[j])
            if s >= TH:
                flagged.append((i, j, round(s, 3)))
    # 클러스터 → distinct: 그룹당 1개(관주 우선 유지)
    clusters = uf([(i, j) for i, j, _ in flagged], n)
    keep = set()
    for g in clusters:
        k = next((i for i in g if flat[i]["gwanju"]), g[0])
        keep.add(k)
    distinct = sorted(keep)
    return qt, variants, flat, flagged, distinct, cost


for date in sys.argv[1:] or ["2026-07-30", "2026-07-31", "2026-08-01"]:
    qt, variants, flat, flagged, distinct, cost = run_day(date)
    n = len(flat)
    gwi = [i for i, f in enumerate(flat) if f["gwanju"]]
    print(f"\n=== {date} · {qt.get('scripture_ref')} · 본따 {len(variants) or 1}개 ===")
    print(f"[9개 고정] 답변 겹침 쌍(≥0.75): {len(flagged)}건 · 관주 슬롯 {[i+1 for i in gwi]}")
    for i, j, s in sorted(flagged, key=lambda x: -x[2]):
        print(f"   뜻 {s}  · {flat[i]['q']}")
        print(f"          · {flat[j]['q']}")
    print(f"[정직한 가변] 겹침 빼고 distinct = {len(distinct)}개 (겹침 쌍 0 보장) · 관주 {'포함' if any(flat[i]['gwanju'] for i in distinct) else '없음'}")
    for k, i in enumerate(distinct):
        mark = " 🔗관주" if flat[i]["gwanju"] else ""
        print(f"   {k+1}.{mark} {flat[i]['q']}")
    json.dump({"date": date, "n": n, "flagged": flagged, "distinct": distinct,
               "questions": flat, "gwanju_slots": gwi, "cost_krw": round(cost.get("cost_krw", 0), 1)},
              open(OUT / f"{date}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"   (비용 {round(cost.get('cost_krw',0),1)}원)")
