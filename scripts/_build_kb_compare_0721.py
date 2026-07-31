"""KB형 출처 기록 — 도입 전후 비교 HTML. ※ 로컬 도구(_접두사).

사장님 요청(2026-07-21): KB형이 중복·배경지식에 실제로 어떤 영향인지, 정확한 건수와 함께.

두 측정 라운드를 나란히 비교한다:
  이전  : scripts/_repeat_v3_capfix/  (KB형 없음, 카테고리 상한만)
  현재  : scripts/_repeat/            (KB형 추가)
둘 다 4일(7/14~17) × 3회 = 12회. 겹침은 답변 임베딩(_measure_answer_overlap).

사용: python scripts/_build_kb_compare_0721.py
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
OUT = Path(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\KB형_비교_0721.html")
PREV_DIR = REPO / "scripts" / "_repeat_v3_capfix"
CUR_DIR = REPO / "scripts" / "_repeat"
SAFE = ("인물 배경", "문화·관습", "어원·유래", "지명 정보")


def esc(s):
    return html.escape(str(s if s is not None else ""))


def round_stats(results):
    ov = [r["overlap"] for v in results.values() for r in v["runs"]]
    zero = sum(1 for x in ov if x == 0)
    return {"runs": len(ov), "zero": zero, "sum": sum(ov),
            "zrate": zero / len(ov) * 100 if ov else 0,
            "kb": st.mean([r.get("kb_used", 0) for v in results.values() for r in v["runs"]]) if ov else 0,
            "xref": st.mean([r.get("xref_used", 0) for v in results.values() for r in v["runs"]]) if ov else 0,
            "safe": st.mean([r.get("safe_cat", 0) for v in results.values() for r in v["runs"]]) if ov else 0,
            "cost": st.mean([r["cost"] for v in results.values() for r in v["runs"]]) if ov else 0,
            "byrun": {d: [r["overlap"] for r in v["runs"]] for d, v in results.items()}}


def dup_rows():
    """현재 라운드의 겹침쌍 전부 — 출처 종류 표시."""
    rows = []
    typ = Counter()
    for f in sorted(glob.glob(str(CUR_DIR / "*_r*.json"))):
        j = json.loads(Path(f).read_text(encoding="utf-8"))
        sel = {c["question"]: c for c in j["meta"]["candidates"] if c.get("selected")}
        r = mo.analyze(f)
        name = Path(f).stem.replace("2026-", "")
        for p in r["sim_flagged"]:
            a, b = r["qs"][p["i"]], r["qs"][p["j"]]
            ta = sel.get(a["question"], {}).get("anchor_type", "?")
            tb = sel.get(b["question"], {}).get("anchor_type", "?")
            for t in (ta, tb):
                typ[t] += 1
            rows.append((name, p["sim"], ta, tb, a["question"], b["question"]))
    return rows, typ


def kb_breakdown():
    cat, field = Counter(), Counter()
    for f in glob.glob(str(CUR_DIR / "*_r*.json")):
        j = json.loads(Path(f).read_text(encoding="utf-8"))
        for c in j["meta"]["candidates"]:
            if c.get("selected") and c.get("anchor_type") == "KB":
                cat[c["category"]] += 1
                field[str(c.get("anchor", "")).split("#")[0]] += 1
    return cat, field


def main():
    prev = round_stats(json.loads((PREV_DIR / "results.json").read_text(encoding="utf-8")))
    cur = round_stats(json.loads((CUR_DIR / "results.json").read_text(encoding="utf-8")))
    rows, typ = dup_rows()
    kbcat, kbfield = kb_breakdown()

    def byrun_html(stats):
        out = ""
        for d, ov in stats["byrun"].items():
            z = sum(1 for x in ov if x == 0)
            cls = "good" if z == len(ov) else ("bad" if z == 0 else "warn")
            out += (f'<tr><td>{d[5:]}</td><td class="n">{" · ".join(str(x) for x in ov)}</td>'
                    f'<td class="n"><span class="pill {cls}">{z}/{len(ov)}</span></td></tr>')
        return out

    dup_html = ""
    for name, sim, ta, tb, q1, q2 in sorted(rows, key=lambda x: -x[1]):
        kbmark = " kb" if "KB" in (ta, tb) else ""
        dup_html += (f'<div class="dup{kbmark}"><div class="dh"><b>{sim:.2f}</b> '
                     f'<span class="rn">{name[3:]}</span> '
                     f'<span class="ty">{esc(ta)}↔{esc(tb)}</span></div>'
                     f'{esc(q1)}<br>{esc(q2)}</div>')

    tv = sum(typ.values())
    typ_html = "".join(
        f'<tr><td>{t}형</td><td class="n">{typ.get(t, 0)}회</td>'
        f'<td class="bar"><i style="width:{typ.get(t, 0) / (tv or 1) * 100 * 2.4:.0f}px"></i></td></tr>'
        for t in ("본문", "관주", "KB"))

    kbcat_html = "".join(f'<tr><td>{esc(k)}{" 🟢" if k in SAFE else ""}</td>'
                         f'<td class="n">{v}</td></tr>' for k, v in kbcat.most_common())

    def delta(a, b, unit="", inv=False):
        d = b - a
        good = (d < 0) if inv else (d > 0)
        cls = "up" if good else ("down" if d else "flat")
        sign = "+" if d > 0 else ""
        return f'<span class="d {cls}">{sign}{d:.0f}{unit}</span>'

    CSS = """
*{box-sizing:border-box}body{margin:0;background:#f5f5f7;color:#1d1d1f;line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:0 18px 60px}
header{text-align:center;padding:44px 18px 22px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.02em}
header p{margin:0;color:#6e6e73;font-size:14px}
section{background:#fff;border-radius:18px;padding:22px 24px;margin:16px 0;
box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 20px rgba(0,0,0,.05)}
h2{font-size:19px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:#6e6e73;font-size:13.5px;margin:0 0 15px}
.vs{display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:center;margin:6px 0}
.card{background:#fafafa;border-radius:14px;padding:16px;text-align:center}
.card.now{background:#f4f9ff;border:1px solid rgba(0,113,227,.15)}
.card h3{margin:0 0 8px;font-size:12px;color:#6e6e73;font-weight:600}
.card b{font-size:30px;letter-spacing:-.02em;display:block}
.card span{font-size:12px;color:#6e6e73}
.arrow{font-size:20px;color:#c7c7cc}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:8px;border-bottom:1px solid #ececf0;text-align:left}
th{font-size:11px;color:#86868b;text-transform:uppercase;letter-spacing:.03em}
td.n{text-align:center}
.pill{display:inline-block;padding:1px 9px;border-radius:999px;font-size:11px;font-weight:600}
.pill.good{background:rgba(52,199,89,.15);color:#248a3d}
.pill.warn{background:rgba(255,159,10,.18);color:#a85f00}
.pill.bad{background:rgba(255,59,48,.13);color:#c9251c}
.bar i{display:inline-block;height:9px;background:#0071e3;border-radius:5px;opacity:.7;vertical-align:middle}
.d{font-size:12px;font-weight:700;padding:1px 7px;border-radius:6px;margin-left:5px}
.d.up{background:rgba(52,199,89,.16);color:#248a3d}
.d.down{background:rgba(255,59,48,.14);color:#c9251c}
.d.flat{background:#f0f0f3;color:#86868b}
.dup{background:#fff6f6;border:1px solid rgba(255,59,48,.18);border-radius:10px;
padding:9px 12px;margin:7px 0;font-size:12.5px;color:#6b2018}
.dup.kb{border-color:rgba(0,113,227,.35);background:#f4f8ff;color:#1a3a5c}
.dh{margin-bottom:3px}.dh b{font-size:14px}
.rn{font-size:11px;color:#86868b;margin:0 4px}
.ty{font-size:10px;background:#00000010;padding:1px 6px;border-radius:5px}
.note{border-left:3px solid #0071e3;background:#f4f9ff;padding:12px 15px;border-radius:0 10px 10px 0;
margin:13px 0;font-size:13.5px}
.note.warn{border-color:#ff9f0a;background:#fff9f0}
.note.bad{border-color:#ff3b30;background:#fff5f5}
.big{font-size:15px;font-weight:600}
@media(prefers-color-scheme:dark){body{background:#000;color:#f5f5f7}
header p,.sub,th{color:#98989d}section{background:#1c1c1e}
.card{background:#2c2c2e}.card.now{background:#0d1b2e}
th,td{border-color:#38383a}.dup{background:#2a1416;color:#ffb0a8}
.dup.kb{background:#0d1b2e;color:#a8cef0}.ty{background:#ffffff18}
.note{background:#0d1b2e}.note.warn{background:#2a1f0d}.note.bad{background:#2a1214}}
"""

    doc = f"""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KB형 출처 기록 — 도입 전후 비교</title><style>{CSS}</style>
<header>
  <h1>KB형 출처 기록 — 도입 전후 비교</h1>
  <p>4일(7/14~17) × 3회 = 12회씩 · 겹침은 답변 임베딩(뜻)으로 측정</p>
</header>
<div class="wrap">

<section>
  <h2>한눈 비교</h2>
  <p class="sub">KB형 = 인물·주의점·해석 재료를 질문 근거로 쓰는 새 출처 종류(예: "나단은 누구?")</p>
  <div class="vs">
    <div class="card"><h3>이전 (KB형 없음)</h3><b>{prev['zrate']:.0f}%</b>
      <span>중복 0건 달성률</span></div>
    <div class="arrow">→</div>
    <div class="card now"><h3>현재 (KB형)</h3><b>{cur['zrate']:.0f}%</b>
      <span>중복 0건 달성률 {delta(prev['zrate'], cur['zrate'], '%p', inv=False)}</span></div>
  </div>
  <table>
    <tr><th>지표</th><th>이전</th><th>현재</th><th>변화</th></tr>
    <tr><td>중복 0건 달성률</td><td class="n">{prev['zrate']:.0f}% ({prev['zero']}/12)</td>
        <td class="n">{cur['zrate']:.0f}% ({cur['zero']}/12)</td><td class="n">{delta(prev['zrate'], cur['zrate'], '%p')}</td></tr>
    <tr><td>겹침 합계(12회)</td><td class="n">{prev['sum']}건</td>
        <td class="n">{cur['sum']}건</td><td class="n">{delta(prev['sum'], cur['sum'], '건', inv=True)}</td></tr>
    <tr><td>배경지식 비중</td><td class="n">{prev['safe'] / 9 * 100:.0f}%</td>
        <td class="n">{cur['safe'] / 9 * 100:.0f}%</td><td class="n">{delta(prev['safe'] / 9 * 100, cur['safe'] / 9 * 100, '%p')}</td></tr>
    <tr><td>KB형 채택(9개 중)</td><td class="n">0.0</td>
        <td class="n">{cur['kb']:.1f}</td><td class="n">—</td></tr>
    <tr><td>비용</td><td class="n">{prev['cost']:.0f}원</td>
        <td class="n">{cur['cost']:.0f}원</td><td class="n">{delta(prev['cost'], cur['cost'], '원', inv=True)}</td></tr>
  </table>
  <div class="note warn">
    <b class="big">두 지표가 다 조금 나빠졌습니다.</b> 하지만 <b>이 프로젝트는 편차가 매우 큽니다</b> —
    같은 코드로 돌려도 12회 겹침이 3·5·5·10건까지 나왔습니다. 8/12 vs 6/12는 <b>2회 차이</b>라,
    이것만으로 "KB형이 해롭다"고 단정할 수 없습니다. 아래에서 겹침을 하나하나 뜯어봅니다.
  </div>
</section>

<section>
  <h2>정확한 건수 — 현재 라운드 겹침 {len(rows)}건</h2>
  <p class="sub">각 겹침쌍의 출처 종류를 표시했습니다. 파란 카드 = KB형이 낀 것.</p>
  <table style="margin-bottom:14px">
    <tr><th>겹침에 낀 출처 종류</th><th>횟수</th><th></th></tr>
    {typ_html}
  </table>
  <div class="note">
    <b>KB형은 {len(rows)}건 중 {typ.get('KB', 0)}건에만 꼈습니다.</b>
    대부분은 <b>본문형끼리({typ.get('본문', 0)}회 관여)</b>입니다 — KB형이 주범이 아닙니다.
  </div>
  {dup_html}
</section>

<section>
  <h2>진짜 원인 — 특정 본문에 몰려 있습니다</h2>
  <p class="sub">회차별로 보면 문제가 어디서 나는지 분명합니다.</p>
  <table>
    <tr><th>날짜</th><th>회차별 겹침</th><th>0건</th></tr>
    {byrun_html(cur)}
  </table>
  <div class="note bad">
    <b>7/15·7/16이 겹침의 대부분을 만듭니다. 둘 다 삼하 7장(다윗 언약)입니다.</b>
    장 전체가 "집을 지어주겠다"는 약속 하나로 이어져, <b>절을 나눠도 답이 같은 주제로 수렴</b>합니다.
    출처 기록은 '본문의 다른 자리'까지만 보장하지 '답이 다르다'까지는 못 합니다 — 원리적 한계입니다.<br><br>
    반대로 <b>7/17(삼하 8장, 정복 기록)은 3회 다 0건</b>입니다. 소재가 자연히 갈리는 본문이니까요.
  </div>
</section>

<section>
  <h2>KB형은 왜 배경지식을 못 올렸나</h2>
  <p class="sub">KB형으로 뽑힌 질문 {sum(kbcat.values())}개의 정체.</p>
  <table>
    <tr><th>카테고리</th><th>개수</th></tr>
    {kbcat_html}
  </table>
  <div class="note warn">
    KB형이 여는 재료는 <b>인물(배경지식) + 주의점·신학핵심(신학/해석)</b>이 섞여 있습니다.
    그래서 KB형을 켜도 배경지식 질문만 느는 게 아니라 <b>신학 질문도 같이 늘어</b>, 순효과가 흐릿합니다.
    게다가 KB형 채택 자체가 <b>9개 중 {cur['kb']:.1f}개</b>로 적습니다 — 관주형과 같은 "만들어놨는데 잘 안 씀" 문제입니다.
  </div>
</section>

<section>
  <h2>결론 — 지금 커밋하면 안 됩니다</h2>
  <div class="note">
    <b>KB형 메커니즘은 기술적으로 잘 작동합니다</b> — "나단은 누구?" 같은 질문을 실제로 만들고, 검증도 통과합니다.
    <b>그러나 지금 켠 채로는 중복·배경지식 어느 쪽에도 도움이 확인되지 않습니다.</b><br><br>
    처방 후보:<br>
    ① KB형을 <b>인물 재료로만 제한</b>(주의점·신학핵심 빼기) — 배경지식만 열고 신학 유입 차단<br>
    ② <b>신학/해석 견해 상한</b>이 여전히 안 걸리는 버그부터 고치기<br>
    ③ 7/15·7/16형(단일 주제 장)은 출처 기록 밖의 문제 — 별도 접근 필요<br><br>
    <b>다음 판단은 ①을 적용해 다시 12회 측정한 뒤에.</b> 한 라운드로는 편차와 구별이 안 됩니다.
  </div>
</section>

</div>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"생성: {OUT}\n  {len(doc):,}자 · 겹침 {len(rows)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
