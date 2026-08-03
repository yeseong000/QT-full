# -*- coding: utf-8 -*-
"""'중복을 관주로 교체' 방식.
9개를 뽑은 뒤 → 의미 중복 쌍 감지(gpt-4o 1회) → 중복인 질문을 버리고
그 슬롯을 '검증된 배경지식형 관주'(없으면 다른 distinct 후보)로 교체 → 저장.
사용: python gen_replace.py <mode> <date...>   (mode 예: replace)
"""
import sys, json
from pathlib import Path
from collections import Counter

EXP = Path(r"C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER\3146c29a-330a-4a5d-a385-72ab7951f69b\scratchpad\qt-exp")
OUTROOT = Path(__file__).parent / "exp_out"
sys.path.insert(0, str(EXP / "scripts"))
import generate_meditation as gm
import followup_simple as fs

# 감지용 판정기(교체 트리거) — 채점(analyze_dup_exp)과 독립되게 프롬프트를 달리 쓴다.
env = {}
for line in open(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\.env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k] = v
from openai import OpenAI
client = OpenAI(api_key=env["OPENAI_API_KEY"])

DETECT_SYS = """성경 QT 질문 9개를 받는다. '답을 쓰면 사실상 같은 지식·같은 대목을 설명하게 되는' 질문끼리 묶어라.
- 같은 인물·사건·대상을 같은 각도로 다시 묻는 쌍이 핵심. 표현이 달라도 답이 겹치면 한 묶음.
- 대상이 다르거나, 같은 대상이라도 전혀 다른 국면(정체 vs 동기)이면 묶지 마라.
출력 JSON: {"dups":[[index,...], ...]}  (2개 이상 겹치는 묶음만)"""


def detect_dups(qs):
    idxq = [{"index": i, "question": q} for i, q in enumerate(qs)]
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": DETECT_SYS},
                  {"role": "user", "content": json.dumps({"질문들": idxq}, ensure_ascii=False)}],
        temperature=0.0, max_tokens=800, response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content).get("dups", [])


def _silent(*a, **k):
    pass


def build_pool_tree(date):
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
    return qt, variants, pool, tree, cost


def replace_dups_with_gwanju(pool, tree):
    """9개 중 의미 중복을 감지 → 중복 질문을 버리고 관주(우선)로 교체."""
    nodes = []
    for m in tree:
        nodes.append(m)
        for t in m["follow_ups"]:
            nodes.append(t)
    qs = [n["question"] for n in nodes]
    q2c = {fs.fp._norm(c["q"]): c for c in pool}
    dups = detect_dups(qs)

    # 각 묶음에서 최저 index만 남기고 나머지를 교체 대상으로
    to_replace = []
    for g in dups:
        gg = sorted(set(int(i) for i in g if 0 <= int(i) < len(nodes)))
        for idx in gg[1:]:
            to_replace.append(idx)
    to_replace = sorted(set(to_replace))

    # 남는(안 뽑힌) 검증된 후보 = 교체 재고. 관주 먼저.
    sel_norm = {fs.fp._norm(q) for q in qs}
    spares = [c for c in pool if not c.get("sel") and c["anchor_ok"] and fs.fp._norm(c["q"]) not in sel_norm]
    gwanju = [c for c in spares if c["anchor_type"] == "관주"]
    others = [c for c in spares if c["anchor_type"] != "관주"]
    # 유지되는 질문들의 지식묶음(cluster) — 교체분이 이것과 겹치면 안 됨
    kept_clusters = set()
    for i, n in enumerate(nodes):
        if i not in to_replace:
            c = q2c.get(fs.fp._norm(n["question"]))
            if c: kept_clusters.add(c["cluster"])

    log = []
    for idx in to_replace:
        pick = next((c for c in gwanju if c["cluster"] not in kept_clusters), None) \
            or next((c for c in others if c["cluster"] not in kept_clusters), None)
        if not pick:
            log.append(f"슬롯{idx}: 교체 재고 없음(그대로 둠)")
            continue
        old = nodes[idx]["question"][:22]
        nodes[idx]["question"] = pick["q"]
        nodes[idx]["category"] = pick["cat"]
        nodes[idx]["topic"] = pick["topic"]
        nodes[idx]["_atype"] = pick["anchor_type"]
        kept_clusters.add(pick["cluster"])
        (gwanju if pick in gwanju else others).remove(pick)
        tag = "관주" if pick["anchor_type"] == "관주" else pick["anchor_type"]
        log.append(f"슬롯{idx}: '{old}' → [{tag}] '{pick['q'][:24]}'")
    return nodes, dups, to_replace, log, q2c


def run(mode, dates):
    outdir = OUTROOT / mode
    outdir.mkdir(parents=True, exist_ok=True)
    n_main3 = 0
    for date in dates:
        try:
            qt, variants, pool, tree, cost = build_pool_tree(date)
            nodes, dups, to_replace, rlog, q2c = replace_dups_with_gwanju(pool, tree)

            def atype(i):
                n = nodes[i]
                return n.get("_atype") or (q2c.get(fs.fp._norm(n["question"])) or {}).get("anchor_type")
            fq, gw = [], []
            k = 0
            for m in tree:  # tree 구조 유지(메인3+꼬리6), nodes와 같은 순서
                if atype(k) == "관주" or nodes[k].get("category") == "연결 질문":
                    gw.append(k)
                item = {"question": nodes[k]["question"], "answer": "", "follow_ups": []}
                k += 1
                for _ in m["follow_ups"]:
                    if atype(k) == "관주" or nodes[k].get("category") == "연결 질문":
                        gw.append(k)
                    item["follow_ups"].append({"question": nodes[k]["question"], "answer": ""})
                    k += 1
                fq.append(item)
            m3 = 6 in gw
            n_main3 += 1 if m3 else 0
            out = {"date": date, "scripture_ref": qt.get("scripture_ref", ""), "title": qt.get("title", ""),
                   "variants": variants, "follow_up_questions": fq,
                   "_gwanju_slots": gw, "_gwanju_in_main3": m3,
                   "_dups_detected": dups, "_replaced_slots": to_replace, "_replace_log": rlog,
                   "_cost_krw": round(cost.get("cost_krw", 0), 1)}
            json.dump(out, open(outdir / f"{date}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"{date} | 감지중복 {dups} | 교체 {to_replace} | 관주슬롯 {gw} | 메인3={'관주★' if m3 else '-'}")
            for l in rlog:
                print(f"        {l}")
        except Exception as e:
            print(f"{date} | 실패: {e}")
    print(f"\n메인3 관주 {n_main3}/{len(dates)}일 · 저장 {outdir}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "replace"
    dates = sys.argv[2:] or ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-25", "2026-07-26"]
    run(mode, dates)
