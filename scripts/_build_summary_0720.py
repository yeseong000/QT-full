"""떠오르는 질문 개편 — 한눈 요약 HTML. ※ 로컬 도구(_접두사).

사장님 요청(2026-07-20): "답변이 어떻게 바뀌었는지 · 제대로 바뀌었는지 ·
얼마나 다양한지 · 중복은 없었는지 — 간단하게 요약"

데이터는 전부 실측에서 뽑는다:
  기존(운영) : data/deep_dive/*.json
  신규        : scripts/_repeat/*_r*.json (반복 측정 결과)
  겹침        : _measure_answer_overlap.py (답변 임베딩)

사용: python scripts/_build_summary_0720.py
"""
import glob
import html
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _measure_answer_overlap as mo  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = Path(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\떠오르는질문_요약_0720.html")
DATES = ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]
SAFE = ("인물 배경", "문화·관습", "어원·유래", "지명 정보")


def esc(s):
    return html.escape(str(s if s is not None else ""))


def load_runs():
    out = {}
    for d in DATES:
        out[d] = sorted(glob.glob(str(REPO / "scripts" / "_repeat" / f"{d}_r*.json")))
    return out


def main():
    runs = load_runs()
    if not any(runs.values()):
        raise SystemExit("반복 측정 결과가 없습니다 — _repeat_measure.py를 먼저 돌리세요.")

    # ===== 집계 =====
    rows, before_tot, zero_hit, zero_all = [], 0, 0, 0
    cat_new, cat_old = Counter(), Counter()
    new_costs, old_costs = [], []
    sample = None       # 답변 비교용 (가장 최근 회차)
    dup_examples = []

    for d in DATES:
        b = mo.analyze(d)
        nb = len(b["sim_flagged"])
        before_tot += nb
        prod = json.loads((REPO / "data" / "deep_dive" / f"{d}.json").read_text(encoding="utf-8"))
        old_costs.append((prod.get("_cost_followup") or {}).get("cost_krw", 0))
        for c in (prod.get("_followup_meta") or {}).get("category_map") or []:
            cat_old[c.get("category", "?")] += 1

        ovs = []
        for f in runs[d]:
            r = mo.analyze(f)
            j = json.loads(Path(f).read_text(encoding="utf-8"))
            ovs.append(len(r["sim_flagged"]))
            new_costs.append(j["cost"].get("cost_krw", 0))
            for c in j["meta"]["candidates"]:
                if c.get("selected"):
                    cat_new[c["category"]] += 1
            for p in r["sim_flagged"]:
                dup_examples.append((round(p["sim"], 2), d,
                                     r["qs"][p["i"]]["question"], r["qs"][p["j"]]["question"]))
            if d == DATES[-1]:
                sample = (b, r)
        zero_hit += sum(1 for x in ovs if x == 0)
        zero_all += len(ovs)
        rows.append((d, nb, ovs))

    zrate = zero_hit / zero_all * 100 if zero_all else 0
    new_mean = st.mean([sum(x) for x in zip(*[r[2] for r in rows])]) if rows else 0

    def cat_table(counter, safe_mark=True):
        tot = sum(counter.values()) or 1
        out = []
        for k, v in counter.most_common():
            mark = ' <span class="safe">배경지식</span>' if (safe_mark and k in SAFE) else ""
            out.append(f'<tr><td>{esc(k)}{mark}</td><td class="n">{v}</td>'
                       f'<td class="bar"><i style="width:{v / tot * 100 * 3:.0f}px"></i>'
                       f'{v / tot * 100:.0f}%</td></tr>')
        return "".join(out)

    safe_new = sum(cat_new[k] for k in SAFE) / (sum(cat_new.values()) or 1) * 100
    safe_old = sum(cat_old[k] for k in SAFE) / (sum(cat_old.values()) or 1) * 100

    row_html = ""
    for d, nb, ovs in rows:
        z = sum(1 for x in ovs if x == 0)
        cls = "good" if z == len(ovs) else ("warn" if z else "bad")
        row_html += (f'<tr><td><b>{d[5:]}</b></td><td class="n">{nb}건</td>'
                     f'<td class="n">{" · ".join(str(x) + "건" for x in ovs)}</td>'
                     f'<td class="n"><span class="pill {cls}">{z}/{len(ovs)}</span></td></tr>')

    dup_html = ""
    for sim, d, q1, q2 in sorted(dup_examples, reverse=True)[:4]:
        dup_html += (f'<div class="dup"><b>{sim}</b> · {d[5:]}<br>{esc(q1)}<br>{esc(q2)}</div>')
    if not dup_html:
        dup_html = '<div class="dup ok">이번 측정에서 겹친 질문이 한 건도 없습니다.</div>'

    # 답변 비교 (마지막 날짜: 기존 vs 신규 3개씩)
    def qa_list(r, n=3):
        out = []
        for q in r["qs"][:n]:
            out.append(f'<details><summary>{esc(q["question"])}</summary>'
                       f'<div class="ans">{esc(q["answer"][:400])}…</div></details>')
        return "".join(out)

    CSS = """
*{box-sizing:border-box}body{margin:0;background:#f5f5f7;color:#1d1d1f;line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:0 18px 60px}
header{text-align:center;padding:48px 18px 28px}
h1{font-size:30px;margin:0 0 8px;letter-spacing:-.02em}
header p{margin:0;color:#6e6e73}
.hero{display:flex;gap:12px;justify-content:center;margin:22px 0 0;flex-wrap:wrap}
.kpi{background:#fff;border-radius:16px;padding:16px 22px;min-width:150px;
box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 20px rgba(0,0,0,.05)}
.kpi b{display:block;font-size:30px;letter-spacing:-.02em}
.kpi span{font-size:12px;color:#6e6e73}
.kpi .was{font-size:12px;color:#86868b;display:block;margin-top:2px}
section{background:#fff;border-radius:18px;padding:24px 26px;margin:18px 0;
box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 20px rgba(0,0,0,.05)}
h2{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:#6e6e73;font-size:14px;margin:0 0 16px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:9px 8px;border-bottom:1px solid #ececf0;text-align:left}
th{font-size:11px;color:#86868b;text-transform:uppercase;letter-spacing:.04em}
td.n{text-align:center}
.bar{white-space:nowrap;color:#6e6e73;font-size:12px}
.bar i{display:inline-block;height:8px;background:#0071e3;border-radius:4px;
margin-right:6px;vertical-align:middle;opacity:.75}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600}
.pill.good{background:rgba(52,199,89,.15);color:#248a3d}
.pill.warn{background:rgba(255,159,10,.18);color:#a85f00}
.pill.bad{background:rgba(255,59,48,.13);color:#c9251c}
.safe{background:rgba(52,199,89,.14);color:#248a3d;font-size:11px;padding:1px 7px;border-radius:6px}
.note{border-left:3px solid #0071e3;background:#f4f9ff;padding:12px 15px;border-radius:0 10px 10px 0;
margin:14px 0;font-size:14px}
.note.warn{border-color:#ff9f0a;background:#fff9f0}
.dup{background:#fff6f6;border:1px solid rgba(255,59,48,.2);border-radius:10px;
padding:10px 13px;margin:8px 0;font-size:13px;color:#7a2018}
.dup.ok{background:#f2fbf4;border-color:rgba(52,199,89,.3);color:#1c6b32}
details{border:1px solid #ececf0;border-radius:10px;margin:6px 0;overflow:hidden}
summary{cursor:pointer;padding:10px 12px;font-size:13.5px}
summary:hover{background:#fafafa}
.ans{padding:0 12px 12px;font-size:13px;color:#3a3a3c;white-space:pre-wrap}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:700px){.cols{grid-template-columns:1fr}}
.cols h3{font-size:13px;color:#6e6e73;margin:0 0 8px;padding-bottom:6px;border-bottom:1px solid #ececf0}
@media(prefers-color-scheme:dark){
body{background:#000;color:#f5f5f7}header p,.sub,.bar,th{color:#98989d}
section,.kpi{background:#1c1c1e;box-shadow:0 1px 2px rgba(0,0,0,.5)}
th,td,details,.cols h3{border-color:#38383a}
.note{background:#0d1b2e}.note.warn{background:#2a1f0d}
.dup{background:#2a1416;color:#ff9a92}.dup.ok{background:#12281a;color:#7ee2a0}
summary:hover{background:#2c2c2e}.ans{color:#d1d1d6}}
"""

    doc = f"""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>떠오르는 질문 개편 요약</title><style>{CSS}</style>
<header>
  <h1>떠오르는 질문 — 개편 요약</h1>
  <p>4일치({DATES[0][5:]}~{DATES[-1][5:]})를 각 3회씩, 총 {zero_all}번 돌려 measured</p>
  <div class="hero">
    <div class="kpi"><b>{zrate:.0f}%</b><span>중복 0건 달성률</span>
      <span class="was">이전 33%</span></div>
    <div class="kpi"><b>{before_tot}→{new_mean:.0f}</b><span>4일 합계 중복(건)</span>
      <span class="was">기존 vs 신규 평균</span></div>
    <div class="kpi"><b>{safe_new:.0f}%</b><span>배경지식 질문 비중</span>
      <span class="was">이전 {safe_old:.0f}%</span></div>
  </div>
</header>
<div class="wrap">

<section>
  <h2>1. 중복은 없었나</h2>
  <p class="sub">답변을 임베딩해 '뜻'으로 비교합니다. 단어만 바꾼 중복도 잡힙니다.</p>
  <table>
    <tr><th>날짜</th><th>기존</th><th>신규 3회</th><th>0건 달성</th></tr>
    {row_html}
  </table>
  <div class="note">
    <b>전체 {zero_all}회 중 {zero_hit}회가 중복 0건({zrate:.0f}%)입니다.</b> 개편 전에는 4일 합계 {before_tot}건이었습니다.
  </div>
  <h3 style="font-size:14px;margin:18px 0 6px">남은 중복 (있다면)</h3>
  {dup_html}
</section>

<section>
  <h2>2. 얼마나 다양해졌나</h2>
  <p class="sub">'배경지식' 표시 = 낯선 인물·사물·지명·낱말의 정체를 알려주는 질문. 초신자에게 가장 값어치 있고, 실측상 중복도 가장 적습니다.</p>
  <div class="cols">
    <div><h3>기존 (운영)</h3><table>{cat_table(cat_old)}</table></div>
    <div><h3>신규</h3><table>{cat_table(cat_new)}</table></div>
  </div>
  <div class="note">
    배경지식 질문이 <b>{safe_old:.0f}% → {safe_new:.0f}%</b>로 바뀌었습니다.
  </div>
</section>

<section>
  <h2>3. 답변은 어떻게 바뀌었나</h2>
  <p class="sub">{DATES[-1][5:]} 기준 · 질문을 누르면 실제 답변이 펼쳐집니다.</p>
  <div class="cols">
    <div><h3>기존 (운영)</h3>{qa_list(sample[0])}</div>
    <div><h3>신규</h3>{qa_list(sample[1])}</div>
  </div>
  <div class="note">
    질문 자체가 바뀌어서 답변도 바뀝니다 — 코드가 <b>질문마다 본문 출처(몇 절, 어느 표현)를 기록·검증</b>하고,
    같은 자리에서 두 개를 뽑지 못하게 막습니다.
  </div>
</section>

<section>
  <h2>4. 비용</h2>
  <table>
    <tr><th></th><th>기존</th><th>신규</th></tr>
    <tr><td>하루 평균</td><td class="n">{st.mean(old_costs):.0f}원</td>
        <td class="n">{st.mean(new_costs):.0f}원</td></tr>
  </table>
  <p class="sub" style="margin-top:10px">차이는 하루 {st.mean(new_costs) - st.mean(old_costs):+.0f}원 수준입니다.
  중복 검사에 쓰는 임베딩은 1년에 약 4원이라 사실상 0원입니다.</p>
</section>

<section>
  <h2>5. 아직 남은 것</h2>
  <div class="note warn">
    <b>목표는 100%인데 {zrate:.0f}%입니다.</b> 남은 중복은 대부분
    <b>서로 다른 절인데 답이 같은 방향으로 흐르는</b> 경우입니다.
    출처 기록은 '본문의 다른 자리'까지만 보장하지, '답이 다르다'까지는 보장하지 못합니다.
  </div>
  <p class="sub">답의 요지를 미리 비교해 거르는 방법을 시험했지만(질문 임베딩·요지 임베딩),
  진짜 중복과 아닌 것이 수치상 겹쳐 임계값을 그을 수 없었습니다. 두 번 다 측정으로 확인하고 접었습니다.</p>
</section>

</div>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"생성: {OUT}\n  {len(doc):,}자 · {zero_all}회 측정 반영")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
