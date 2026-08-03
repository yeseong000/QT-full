# -*- coding: utf-8 -*-
"""개수 가변화: 9개 생성 → 의미중복 감지 → 겹치는 건 버리고 distinct만(관주 포함) 남김.
관주가 몇 번째인지 표시 + 최종 세트 중복률을 gpt-4o 3회 다수결로 독립 채점.
사용: python gen_variable.py <date...>
"""
import sys, json
from pathlib import Path
from collections import Counter, defaultdict

EXP = Path(r"C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER\3146c29a-330a-4a5d-a385-72ab7951f69b\scratchpad\qt-exp")
OUT = Path(__file__).parent / "exp_out" / "variable"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(EXP / "scripts"))
import generate_meditation as gm
import followup_simple as fs

env = {}
for line in open(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\.env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k] = v
from openai import OpenAI
client = OpenAI(api_key=env["OPENAI_API_KEY"])

# 교체 트리거용 감지기(생성 단계)
DETECT_SYS = """성경 QT 질문들을 받는다. '답을 쓰면 사실상 같은 지식·같은 대목을 설명하게 되는' 질문끼리 묶어라.
같은 인물·사건·대상을 같은 각도로 다시 묻는 쌍이 핵심(표현이 달라도 답 겹치면 한 묶음). 대상이 다르거나 전혀 다른 국면이면 묶지 마라.
출력 JSON: {"dups":[[index,...], ...]}  (2개 이상 겹치는 묶음만)"""
# 최종 채점용(감지기와 다른 프롬프트로 독립성 확보)
SCORE_SYS = """성경 QT '떠오르는 질문' 검수자. 독자가 '아까 그거랑 사실상 같은 걸 또 묻네'라고 느낄 만큼 겹치는 질문끼리 묶어라.
같은 대상을 같은 각도로 다시 물으면 중복. 다른 대상이거나 이야기를 진전시키는 다른 국면이면 묶지 마라.
출력 JSON: {"groups":[{"idx":[정수,...]}]}"""


def _judge(sys_prompt, qs, key):
    idxq = [{"index": i, "question": q} for i, q in enumerate(qs)]
    r = client.chat.completions.create(model="gpt-4o",
        messages=[{"role": "system", "content": sys_prompt},
                  {"role": "user", "content": json.dumps({"질문들": idxq}, ensure_ascii=False)}],
        temperature=0.0, max_tokens=900, response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content).get(key, [])


def _silent(*a, **k):
    pass


def build9(date):
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
    nodes = []
    for m in tree:
        nodes.append(m)
        for t in m["follow_ups"]:
            nodes.append(t)
    q2c = {fs.fp._norm(c["q"]): c for c in pool}
    def atype(n):
        return (q2c.get(fs.fp._norm(n["question"])) or {}).get("anchor_type")
    return qt, variants, nodes, atype, cost


def keep_distinct(nodes, atype):
    qs = [n["question"] for n in nodes]
    groups = _judge(DETECT_SYS, qs, "dups")
    drop = set()
    for g in groups:
        gg = sorted(set(int(i) for i in g if 0 <= int(i) < len(nodes)))
        if len(gg) < 2:
            continue
        # 그룹에 관주가 있으면 관주를 남기고, 아니면 최저 index를 남긴다
        keep = next((i for i in gg if atype(nodes[i]) == "관주" or nodes[i].get("category") == "연결 질문"), gg[0])
        for i in gg:
            if i != keep:
                drop.add(i)
    kept = [nodes[i] for i in range(len(nodes)) if i not in drop]
    return kept, groups, sorted(drop)


def score(kept):
    """최종 세트 중복률 — 독립 프롬프트로 3회 다수결."""
    qs = [n["question"] for n in kept]
    n = len(qs)
    votes = Counter()
    for _ in range(3):
        for g in _judge(SCORE_SYS, qs, "groups"):
            idx = sorted(set(int(i) for i in g.get("idx", []) if 0 <= int(i) < n))
            for a in range(len(idx)):
                for b in range(a + 1, len(idx)):
                    votes[(idx[a], idx[b])] += 1
    kept_pairs = [p for p, v in votes.items() if v >= 2]
    involved = set(i for p in kept_pairs for i in p)
    return round(len(involved) / n * 100, 1) if n else 0, kept_pairs


dates = sys.argv[1:] or ["2026-07-30", "2026-07-31", "2026-08-01"]
for date in dates:
    qt, variants, nodes, atype, cost = build9(date)
    kept, groups, dropped = keep_distinct(nodes, atype)
    dup, pairs = score(kept)
    gw = [i for i, n in enumerate(kept) if atype(n) == "관주" or n.get("category") == "연결 질문"]
    out = {"date": date, "scripture_ref": qt.get("scripture_ref", ""), "title": qt.get("title", ""),
           "bontta": len(variants) or 1, "count": len(kept),
           "questions": [{"q": n["question"], "category": n.get("category"),
                          "gwanju": (i in gw)} for i, n in enumerate(kept)],
           "gwanju_index": gw, "dup_rate": dup, "dropped_count": len(dropped),
           "cost_krw": round(cost.get("cost_krw", 0), 1)}
    json.dump(out, open(OUT / f"{date}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n=== {date} · {qt.get('scripture_ref')} · 본따 {out['bontta']}개 ===")
    print(f"9개 생성 → 중복 {len(dropped)}개 버림 → 최종 {len(kept)}개 · 중복률 {dup}% · 관주 {[i+1 for i in gw]}번")
    for i, n in enumerate(kept):
        mark = " 🔗관주" if i in gw else ""
        print(f"  {i+1}. [{n.get('category')}]{mark} {n['question']}")
