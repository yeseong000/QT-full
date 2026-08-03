# -*- coding: utf-8 -*-
"""exp_out/<mode>/*.json 의 재생성 질문에 대해 within-day 중복률(gpt-4o 3회 합의) 측정.
+ 관주가 메인3에 오른 비율. 사용: python analyze_dup_exp.py <mode>
"""
import sys, json, glob
from pathlib import Path
from collections import defaultdict, Counter

SC = Path(__file__).parent
mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
MODEDIR = SC / "exp_out" / mode
N_RUNS = 3

# .env 키 (Desktop)
env = {}
for line in open(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\.env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); env[k] = v
from openai import OpenAI
client = OpenAI(api_key=env["OPENAI_API_KEY"])

WITHIN_SYS = """당신은 성경 QT 앱 '떠오르는 질문' 중복 검수자예요. 한 날짜의 질문 9개(메인 3개 + 각 꼬리 2개)를 받습니다.
독자 입장에서 '아까 그거랑 사실상 같은 걸 또 묻네'라고 느낄 만큼 겹치는 질문끼리 그룹으로 묶으세요.
판정 기준:
- 같은 대상(인물·지명·사물·사건)을 '같은 각도(정의/의미/기능/정체)'로 다시 묻는다 → 중복. strength='강'.
- 같은 대상을 살짝 다른 말로 반복하지만 독자가 겹친다고 느낄 정도 → strength='약'.
- 같은 대상이라도 '다른 국면'을 물어 이야기를 진전시키면 중복 아님 — 묶지 마세요.
- 서로 다른 대상이면 절대 묶지 마세요. 한 질문은 최대 한 그룹에만. 없으면 groups 빈 배열.
입력의 각 질문에는 index(0~8). 출력 JSON:
{"groups":[{"idx":[정수,...],"strength":"강"|"약","subject":"공통 대상","reason":"한 줄"}]}"""


def judge(qs):
    idxq = [{"index": i, "question": q} for i, q in enumerate(qs)]
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": WITHIN_SYS},
                  {"role": "user", "content": json.dumps({"질문들": idxq}, ensure_ascii=False)}],
        temperature=0.0, max_tokens=1500, response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content).get("groups", [])


def uf(pairs, n=9):
    p = list(range(n))
    def f(x):
        while p[x] != x: p[x] = p[p[x]]; x = p[x]
        return x
    for a, b in pairs:
        ra, rb = f(a), f(b)
        if ra != rb: p[rb] = ra
    g = defaultdict(list)
    for i in range(n): g[f(i)].append(i)
    return [sorted(v) for v in g.values() if len(v) > 1]


def flatten(fq):
    qs = []
    for m in fq[:3]:
        qs.append(m.get("question", ""))
        for t in (m.get("follow_ups") or [])[:2]:
            qs.append(t.get("question", ""))
    return qs


rows, rates, m3hits = [], [], 0
for f in sorted(glob.glob(str(MODEDIR / "2026-07-*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    qs = flatten(d["follow_up_questions"])
    if len(qs) != 9:
        print(f"{d['date']} | 질문 {len(qs)}개(9 아님) 건너뜀"); continue
    votes = Counter()
    for _ in range(N_RUNS):
        for g in judge(qs):
            idx = sorted(set(g.get("idx", [])))
            for a in range(len(idx)):
                for b in range(a + 1, len(idx)):
                    votes[(idx[a], idx[b])] += 1
    kept = [p for p, v in votes.items() if v >= 2]
    groups = uf(kept)
    dup_idx = set(i for g in groups for i in g)
    rate = round(len(dup_idx) / 9 * 100, 1)
    rates.append(rate)
    m3 = d.get("_gwanju_in_main3"); m3hits += 1 if m3 else 0
    rows.append((d["date"], rate, groups, m3))
    print(f"{d['date']} | 중복률 {rate}% | 그룹 {groups} | 메인3관주 {'★' if m3 else '-'}")

avg = round(sum(rates) / len(rates), 1) if rates else 0
print(f"\n=== [{mode}] 평균 중복률 {avg}% · 메인3관주 {m3hits}/{len(rows)}일 ===")
json.dump({"mode": mode, "avg_dup": avg, "m3_gwanju": f"{m3hits}/{len(rows)}",
           "days": [{"date": r[0], "dup": r[1], "groups": r[2], "m3": r[3]} for r in rows]},
          open(SC / f"dup_{mode}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
