# -*- coding: utf-8 -*-
"""새 엔진으로 여러 날짜의 '떠오르는 질문'을 재생성(답변 ④ 생략).
각 날짜별로 9개 질문 + 관주 슬롯 정보를 exp_out/<mode>/<date>.json 에 저장.
관주형이 메인3(그리고 어디에)에 오르는지 + 중복 분석 입력을 함께 만든다.
사용: python gen_days.py <mode> <date...>
"""
import sys, json
from pathlib import Path
from collections import Counter

EXP = Path(r"C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER\3146c29a-330a-4a5d-a385-72ab7951f69b\scratchpad\qt-exp")
OUTROOT = Path(__file__).parent / "exp_out"
sys.path.insert(0, str(EXP / "scripts"))
import generate_meditation as gm
import followup_simple as fs

mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
dates = sys.argv[2:] or ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-25", "2026-07-26"]
outdir = OUTROOT / mode
outdir.mkdir(parents=True, exist_ok=True)


def _silent(*a, **k):
    pass


def gen_one(date):
    qt = json.load(open(EXP / "data" / "qt" / f"{date}.json", encoding="utf-8"))
    dd = json.load(open(EXP / "data" / "deep_dive" / f"{date}.json", encoding="utf-8"))
    variants = dd.get("variants") or []
    deep5 = variants[0] if variants else {k: dd.get(k, "") for k in ["장면", "질문", "맥락", "통찰", "연결"]}
    kb = gm.slice_kb_to_passage(gm.load_kb(qt.get("book_name", "")), qt)
    history = gm.load_same_book_followup_history(qt)
    cost = dict(fs._ZERO_COST)

    branches = fs._gen_candidates(gm._fu_chat_v2, qt, kb, deep5, history, cost, log=_silent)
    verdicts, clusters, gists = fs._judge(gm._fu_chat_v2, qt, deep5, branches, cost, log=_silent)
    vmap, xmap, kbmap = fs._verse_map(qt), fs._xref_map(qt), fs._kb_map(fs._usable_kb(kb))
    pool = fs._flatten_pool(branches, verdicts, clusters, vmap, xmap, gists, kbmap)
    pool = fs._gate_clusters(pool, log=_silent)
    tree = fs._assemble_diverse(pool, history, log=_silent)

    # 질문문 → anchor_type 매핑(선택된 트리 노드의 관주 여부 판별)
    q2type = {}
    for c in pool:
        q2type[fs.fp._norm(c.get("q", ""))] = c.get("anchor_type")

    def atype(q):
        return q2type.get(fs.fp._norm(q))

    fq, gwanju_slots = [], []
    slot_idx = 0
    cand_types = Counter(c.get("anchor_type") for c in pool)
    n_gwanju_cand = sum(1 for c in pool if c.get("anchor_type") == "관주")
    for mi, m in enumerate(tree):
        mq = m.get("question", "")
        if atype(mq) == "관주" or m.get("category") == "연결 질문":
            gwanju_slots.append(slot_idx)
        item = {"question": mq, "answer": "", "follow_ups": []}
        slot_idx += 1
        for t in m.get("follow_ups", []):
            tq = t.get("question", "")
            if atype(tq) == "관주" or t.get("category") == "연결 질문":
                gwanju_slots.append(slot_idx)
            item["follow_ups"].append({"question": tq, "answer": ""})
            slot_idx += 1
        fq.append(item)

    out = {
        "date": date, "scripture_ref": qt.get("scripture_ref", ""), "title": qt.get("title", ""),
        "variants": variants, "follow_up_questions": fq,
        "_gwanju_slots": gwanju_slots,               # 관주형이 앉은 슬롯(0=메인1,3=메인2,6=메인3...)
        "_gwanju_in_main3": 6 in gwanju_slots,       # 메인3(슬롯6)이 관주인가
        "_cand_anchor_types": dict(cand_types),
        "_n_gwanju_cand": n_gwanju_cand,
        "_cost_krw": round(cost.get("cost_krw", 0), 1),
    }
    json.dump(out, open(outdir / f"{date}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m3 = "관주★" if out["_gwanju_in_main3"] else "  -  "
    print(f"{date} | 관주후보 {n_gwanju_cand}개 | 관주슬롯 {gwanju_slots} | 메인3={m3} | {out['_cost_krw']}원")
    return out


print(f"=== mode={mode} · {len(dates)}일 재생성 (새 엔진, 답변 생략) ===")
total = 0
for d in dates:
    try:
        o = gen_one(d); total += o["_cost_krw"]
    except Exception as e:
        print(f"{d} | 실패: {e}")
n_main3 = sum(1 for d in dates if (outdir / f"{d}.json").exists() and json.load(open(outdir / f"{d}.json", encoding="utf-8"))["_gwanju_in_main3"])
print(f"\n메인3이 관주인 날: {n_main3}/{len(dates)} · 총비용 {round(total,1)}원 · 저장: {outdir}")
