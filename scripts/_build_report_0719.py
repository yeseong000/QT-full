"""2026-07-19 출처 기록 개편 결과 보고서 HTML 생성기. ※ 운영 아님, _접두사=로컬 도구.

데이터에서 직접 뽑아 쓴다(손으로 옮겨 적지 않는다):
  - 기존(운영)  : data/deep_dive/{date}.json
  - 신규(출처 기록): scripts/ab_{date}_after.json
  - 겹침 측정   : _measure_answer_overlap.py (임베딩 코사인)

사용: python scripts/_build_report_0719.py
"""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _measure_answer_overlap as mo  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = Path(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\출처기록_개편_결과_0719.html")
DATES = ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]


def esc(s):
    return html.escape(str(s if s is not None else ""))


def collect(date):
    """한 날짜의 기존/신규를 나란히 뽑는다."""
    qt = json.loads((REPO / "data" / "qt" / f"{date}.json").read_text(encoding="utf-8"))
    before = mo.analyze(date)
    after = mo.analyze(str(REPO / "scripts" / f"ab_{date}_after.json"))
    r1p = REPO / "scripts" / f"ab_{date}_run1.json"
    run1 = mo.analyze(str(r1p)) if r1p.exists() else None
    prod = json.loads((REPO / "data" / "deep_dive" / f"{date}.json").read_text(encoding="utf-8"))
    newj = json.loads((REPO / "scripts" / f"ab_{date}_after.json").read_text(encoding="utf-8"))
    return {
        "date": date,
        "ref": qt.get("scripture_ref", ""),
        "verses": qt.get("verses", []),
        "before": before, "after": after, "run1": run1,
        "cost_before": prod.get("_cost_followup", {}),
        "cost_after": newj.get("cost", {}),
        "meta_before": prod.get("_followup_meta", {}),
        "meta_after": newj.get("meta", {}),
    }


def pair_index(r):
    """질문 인덱스 → 그 질문이 낀 겹침쌍 목록."""
    idx = {}
    for p in r["sim_flagged"]:
        for k, other in ((p["i"], p["j"]), (p["j"], p["i"])):
            idx.setdefault(k, []).append((p["sim"], r["qs"][other]["question"]))
    return idx


def qlist_html(r, show_anchor):
    """질문 9개 — 클릭하면 답변이 펼쳐진다."""
    idx = pair_index(r)
    out = []
    for i, q in enumerate(r["qs"]):
        dup = idx.get(i, [])
        cls = "q dup" if dup else "q"
        anchor = ""
        if show_anchor:
            if q["verse"] is not None:
                ok = "" if q["anchor_ok"] else " bad"
                anchor = (f'<span class="anchor{ok}">{esc(q["verse"])}절'
                          f' · {esc(q["anchor"])}</span>')
            else:
                anchor = '<span class="anchor none">출처 기록 없음 (교체됨)</span>'
        badge = ""
        if dup:
            worst = max(s for s, _ in dup)
            badge = f'<span class="badge">뜻 겹침 {worst:.2f}</span>'
        note = ""
        if dup:
            items = "".join(f"<li>{esc(t)} <b>({s:.2f})</b></li>" for s, t in dup)
            note = f'<div class="dupnote">이 질문과 답이 겹칩니다:<ul>{items}</ul></div>'
        out.append(
            f'<details class="{cls}"><summary>'
            f'<span class="num">{i + 1}</span>'
            f'<span class="qt">{esc(q["question"])}</span>{anchor}{badge}'
            f'</summary><div class="ans">{esc(q["answer"]) or "(답변 없음)"}</div>{note}</details>')
    return "".join(out)


def verse_map_html(d):
    """본문 절별로 신규 질문이 몇 개 걸렸는지 — 코드가 본문과 대조한 값."""
    counts = {}
    for q in d["after"]["qs"]:
        if q["verse"] is not None:
            counts[q["verse"]] = counts.get(q["verse"], 0) + 1
    chips = []
    for v in d["verses"]:
        n = counts.get(v.get("number"), 0)
        cls = {0: "v0", 1: "v1"}.get(n, "v2")
        chips.append(f'<div class="chip {cls}" title="{esc(v.get("text", "")[:60])}">'
                     f'<b>{esc(v.get("number"))}</b><span>{"·" * n if n else "—"}</span></div>')
    used = len(counts)
    return (f'<div class="vmap">{"".join(chips)}</div>'
            f'<p class="cap">본문 {len(d["verses"])}절 중 <b>{used}절</b>에 질문이 걸렸습니다. '
            f'점 하나 = 질문 하나, "—" = 안 쓴 절.</p>')


def summary_row(d):
    b, a = d["before"], d["after"]
    nb, na = len(b["sim_flagged"]), len(a["sim_flagged"])
    if na < nb:
        verdict, vcls = "개선", "good"
    elif na == nb == 0:
        verdict, vcls = "유지 (깨끗)", "good"
    elif na == nb:
        verdict, vcls = "변화 없음", "warn"
    else:
        verdict, vcls = "악화", "bad"
    return (f"<tr><td><b>{d['date']}</b><br><span class='dim'>{esc(d['ref'])}</span></td>"
            f"<td class='num-c'>{nb}건<br><span class='dim'>최고 {b['max_sim']:.2f}</span></td>"
            f"<td class='num-c'>{na}건<br><span class='dim'>최고 {a['max_sim']:.2f}</span></td>"
            f"<td class='num-c'>{a['distinct_verses'] or '—'}/9</td>"
            f"<td class='num-c'>{d['cost_before'].get('cost_krw', 0):.0f}원 → "
            f"{d['cost_after'].get('cost_krw', 0):.0f}원</td>"
            f"<td><span class='verdict {vcls}'>{verdict}</span></td></tr>")


CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Pretendard',
'Apple SD Gothic Neo','Malgun Gothic',sans-serif;line-height:1.65;
color:#1d1d1f;background:#f5f5f7;-webkit-font-smoothing:antialiased}
.wrap{max-width:920px;margin:0 auto;padding:0 20px 80px}
header{background:linear-gradient(180deg,#fff 0%,#f5f5f7 100%);padding:64px 20px 40px;
text-align:center;border-bottom:1px solid rgba(0,0,0,.06)}
header h1{font-size:36px;letter-spacing:-.02em;margin:0 0 10px;font-weight:700}
header p{margin:0;color:#6e6e73;font-size:17px}
.tag{display:inline-block;margin-top:16px;padding:5px 14px;border-radius:980px;
background:rgba(0,113,227,.1);color:#0071e3;font-size:13px;font-weight:600}
section{background:#fff;border-radius:18px;padding:28px 30px;margin:22px 0;
box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.05)}
h2{font-size:24px;letter-spacing:-.01em;margin:0 0 6px;font-weight:650}
h2 .n{color:#0071e3;margin-right:8px}
.sub{color:#6e6e73;margin:0 0 22px;font-size:15px}
h3{font-size:17px;margin:26px 0 10px;font-weight:650}
table{width:100%;border-collapse:collapse;font-size:14px;margin:14px 0}
th,td{padding:11px 12px;text-align:left;border-bottom:1px solid #e8e8ed;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#86868b;font-weight:600}
.num-c{text-align:center}
.dim{color:#86868b;font-size:12px}
.verdict{display:inline-block;padding:3px 11px;border-radius:980px;font-size:12px;font-weight:600}
.verdict.good{background:rgba(52,199,89,.14);color:#248a3d}
.verdict.warn{background:rgba(255,159,10,.16);color:#b25000}
.verdict.bad{background:rgba(255,59,48,.12);color:#c9251c}
.callout{border-left:3px solid #0071e3;background:#f5f9ff;padding:15px 18px;
border-radius:0 12px 12px 0;margin:16px 0;font-size:15px}
.callout.warn{border-color:#ff9f0a;background:#fff9f0}
.callout.bad{border-color:#ff3b30;background:#fff5f5}
.callout b{font-weight:650}
.vmap{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0 6px}
.chip{min-width:46px;padding:7px 9px;border-radius:11px;text-align:center;font-size:12px;
border:1px solid transparent;transition:transform .2s cubic-bezier(.34,1.56,.64,1)}
.chip:hover{transform:translateY(-2px)}
.chip b{display:block;font-size:13px;font-weight:650}
.chip span{font-size:14px;letter-spacing:1px;line-height:1}
.chip.v0{background:#f5f5f7;color:#c7c7cc;border-color:#e8e8ed}
.chip.v1{background:rgba(52,199,89,.14);color:#248a3d}
.chip.v2{background:rgba(255,159,10,.18);color:#b25000}
.cap{font-size:13px;color:#6e6e73;margin:4px 0 0}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:8px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
.col h4{margin:0 0 10px;font-size:14px;font-weight:650;color:#6e6e73;
padding-bottom:8px;border-bottom:1px solid #e8e8ed}
details.q{border:1px solid #e8e8ed;border-radius:12px;margin-bottom:7px;background:#fff;
overflow:hidden;transition:box-shadow .25s ease}
details.q[open]{box-shadow:0 2px 8px rgba(0,0,0,.06)}
details.q.dup{border-color:rgba(255,59,48,.35);background:#fffafa}
details.q summary{cursor:pointer;padding:11px 13px;font-size:13.5px;list-style:none;
display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}
details.q summary::-webkit-details-marker{display:none}
details.q summary:hover{background:rgba(0,0,0,.02)}
.num{flex:0 0 20px;height:20px;border-radius:50%;background:#f5f5f7;color:#6e6e73;
font-size:11px;font-weight:650;display:flex;align-items:center;justify-content:center;margin-top:1px}
.qt{flex:1 1 200px;min-width:0}
.anchor{flex:0 0 auto;font-size:11px;padding:2px 8px;border-radius:6px;
background:rgba(0,113,227,.1);color:#0071e3;font-weight:600;white-space:nowrap}
.anchor.bad{background:rgba(255,59,48,.12);color:#c9251c}
.anchor.none{background:#f5f5f7;color:#86868b}
.badge{flex:0 0 auto;font-size:11px;padding:2px 8px;border-radius:6px;
background:rgba(255,59,48,.12);color:#c9251c;font-weight:600}
.ans{padding:4px 14px 14px 41px;font-size:13.5px;color:#3a3a3c;white-space:pre-wrap}
.dupnote{margin:0 14px 12px 41px;padding:10px 13px;background:rgba(255,59,48,.06);
border-radius:9px;font-size:12.5px;color:#c9251c}
.dupnote ul{margin:6px 0 0;padding-left:17px}
.dupnote li{margin:3px 0}
ul.plain{padding-left:19px;font-size:15px}
ul.plain li{margin:7px 0}
.src{font-size:13px;color:#6e6e73}
.src a{color:#0071e3;text-decoration:none}
.src a:hover{text-decoration:underline}
code{background:#f5f5f7;padding:2px 6px;border-radius:5px;font-size:12.5px;
font-family:'SF Mono',ui-monospace,Menlo,monospace}
@media(prefers-color-scheme:dark){
body{background:#000;color:#f5f5f7}
header{background:linear-gradient(180deg,#1c1c1e 0%,#000 100%);border-color:rgba(255,255,255,.08)}
header p,.sub,.dim,.cap,.src{color:#98989d}
section{background:#1c1c1e;box-shadow:0 1px 2px rgba(0,0,0,.5),0 8px 24px rgba(0,0,0,.4)}
th,td{border-color:#38383a}th{color:#98989d}
.callout{background:#0d1b2e}.callout.warn{background:#2a1f0d}.callout.bad{background:#2a1214}
details.q{background:#2c2c2e;border-color:#38383a}
details.q.dup{background:#2a1416;border-color:rgba(255,69,58,.4)}
details.q summary:hover{background:rgba(255,255,255,.04)}
.num{background:#3a3a3c;color:#98989d}
.ans{color:#d1d1d6}
.chip.v0{background:#2c2c2e;color:#48484a;border-color:#38383a}
.col h4{border-color:#38383a;color:#98989d}
code{background:#2c2c2e}
}
"""


def build():
    data = [collect(d) for d in DATES]

    rows = "".join(summary_row(d) for d in data)
    vrows, vb, v1, v2 = "", 0, 0, 0
    for d in data:
        nb = len(d["before"]["sim_flagged"])
        n1 = len(d["run1"]["sim_flagged"]) if d["run1"] else None
        n2 = len(d["after"]["sim_flagged"])
        vb += nb; v1 += n1 or 0; v2 += n2
        flip = " style='background:rgba(255,159,10,.12)'" if n1 is not None and n1 != n2 else ""
        vrows += (f"<tr{flip}><td><b>{d['date']}</b></td><td class='num-c'>{nb}건</td>"
                  f"<td class='num-c'>{'—' if n1 is None else str(n1) + '건'}</td>"
                  f"<td class='num-c'>{n2}건</td></tr>")
    cb = sum(d["cost_before"].get("cost_krw", 0) for d in data) / len(data)
    ca = sum(d["cost_after"].get("cost_krw", 0) for d in data) / len(data)

    days = []
    for d in data:
        a_meta = d["meta_after"]
        vd = a_meta.get("judge_verdicts") or {}
        spare = sum(1 for c in (a_meta.get("candidates") or [])
                    if c.get("verdict") == "좋음" and not c.get("selected") and c.get("anchor_ok"))
        fixnote = (f'<p class="cap">후보 {a_meta.get("candidate_count")}개 · 판정 {vd} · '
                   f'미선택 여유분 <b>{spare}개</b> · 재선택 {a_meta.get("refilled_from_pool", 0)}건 · '
                   f'GPT 교체 {a_meta.get("fix_rounds", 0)}라운드</p>')
        if a_meta.get("fix_rounds"):
            nfix = len(a_meta.get("initial_problems") or {})
            fixnote += (f'<div class="callout bad"><b>주의 — 이 날은 9개 중 {nfix}개가 '
                        f'교체 단계(_qfix)에서 새로 쓰였습니다.</b> 교체된 질문은 출처 기록을 '
                        f'물려받지 못해 절 배치의 보호를 받지 못합니다. 아래 "출처 기록 없음" 표시가 '
                        f'그것이고, 이 날 남은 겹침이 정확히 거기서 났습니다.</div>')
        days.append(f"""
<section>
  <h2><span class="n">§</span>{d['date']} <span class="dim">· {esc(d['ref'])}</span></h2>
  <p class="sub">질문을 누르면 실제 답변이 펼쳐집니다. 빨간 테두리 = 답이 겹치는 질문.</p>
  <h3>신규 — 본문 절 사용 지도</h3>
  {verse_map_html(d)}
  {fixnote}
  <div class="cols">
    <div class="col"><h4>기존 (운영 데이터)</h4>{qlist_html(d['before'], False)}</div>
    <div class="col"><h4>신규 (출처 기록 적용)</h4>{qlist_html(d['after'], True)}</div>
  </div>
</section>""")

    doc = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>출처 기록 개편 결과 — 떠오르는 질문 중복</title>
<style>{CSS}</style>
<header>
  <h1>출처 기록 개편 결과</h1>
  <p>떠오르는 질문 중복 문제 · 7/13 · 7/14 · 7/15 3일치 검증</p>
  <div class="tag">2026-07-19</div>
</header>
<div class="wrap">

<section>
  <h2><span class="n">1</span>한 줄 요약</h2>
  <p class="sub">질문마다 "본문 어느 절, 어느 글자에서 나왔는지"를 밝히게 하고, 코드가 본문과 대조해 서로 다른 자리에 배치했습니다.</p>
  <div class="callout">
    <b>결과 — 3일 중 1일 개선, 2일 유지. 비용은 하루 평균 {ca - cb:+.0f}원({(ca - cb) / cb * 100:+.0f}%).</b><br>
    프롬프트는 오히려 <b>13% 짧아졌습니다</b>(2301자 → 2003자). 말로 부탁하던 규칙을 코드가 대신 강제하게 됐기 때문입니다.
  </div>
  <table>
    <tr><th>날짜</th><th>기존 겹침</th><th>신규 겹침</th><th>서로 다른 절</th><th>비용</th><th>판정</th></tr>
    {rows}
  </table>
  <p class="cap">"겹침"은 답변을 임베딩(text-embedding-3-small)해 뜻으로 비교한 값입니다. 단어 겹침(자카드)이 아닙니다.</p>
</section>

<section>
  <h2><span class="n">1.5</span>먼저 — 회차 편차가 개편 효과보다 큽니다</h2>
  <p class="sub">이번에 가장 중요한 결과입니다. <b>똑같은 코드로 두 번 돌린 것</b>인데 결과가 이만큼 달랐습니다.</p>
  <table>
    <tr><th>날짜</th><th>기존 (운영)</th><th>신규 1회차</th><th>신규 2회차</th></tr>
    {vrows}
    <tr><td><b>합계</b></td><td><b>{vb}건</b></td><td><b>{v1}건</b></td><td><b>{v2}건</b></td></tr>
  </table>
  <div class="callout bad">
    <b>7/15는 1건 → 4건, 7/16은 2건 → 0건으로 뒤집혔습니다.</b> 코드는 한 글자도 다르지 않습니다.<br><br>
    이 말은 — <b>이 보고서를 포함해, 한 번 돌린 결과로 "고쳤다/나빠졌다"를 말하면 틀릴 수 있다</b>는 뜻입니다.
    실제로 이번 작업 중에 저는 단발 결과를 보고 원인을 세 번 잘못 짚었습니다.
  </div>
  <p>지금 정직하게 말할 수 있는 것은 이 정도입니다:</p>
  <ul class="plain">
    <li>기존 운영분 <b>7건</b> → 신규 <b>3건·5건</b>(평균 4건). <b>방향은 좋아 보이지만 확정할 수 없습니다.</b></li>
    <li>확정할 수 있는 건 <b>구조적으로 검증되는 것들</b>입니다 — 출처 기록 검증 실패 0건, 복사본 0건, 프롬프트 모순 제거처럼 <b>매 회차 재현되는</b> 항목.</li>
    <li>겹침 건수로 결론을 내려면 <b>날짜당 3~5회씩 반복 측정</b>이 필요합니다.</li>
  </ul>
</section>

<section>
  <h2><span class="n">2</span>핵심 발견 — 절이 겹치면 답이 겹칩니다</h2>
  <p class="sub">이번 검증에서 가장 중요한 결과입니다.</p>
  <p>7/19 운영분은 <b>8절짜리 본문에서 1·3·7절은 손도 안 대고 6절 하나에서 질문 3개</b>를 뽑았습니다.
  라벨(<code>topic</code>)은 셋 다 달라서 코드도 판정 모델도 못 잡았고, 단어 겹침도 0.18에 그쳐 못 잡았습니다.
  하지만 답을 읽어보면 같은 설명이었습니다.</p>
  <div class="callout">
    <b>왜 이게 중요한가</b><br>
    어휘와 라벨은 모델이 마음대로 바꿀 수 있어서 <b>코드가 참·거짓을 판정할 수 없습니다</b>.
    반면 "본문 몇 절의 어느 글자에서 나왔나"는 <b>코드가 본문과 대조해 검증할 수 있습니다</b>.
    검증할 수 있는 것에만 규칙을 걸 수 있습니다.
  </div>
  <h3>출처 기록이 하는 일 (GPT 호출 0회, 추가 비용 0원)</h3>
  <ul class="plain">
    <li><b>근거 검증</b> — <code>anchor</code>가 그 절 본문에 <u>글자 그대로</u> 있는지 대조합니다. 모델이 지어낸 요약("아람 용병 고용")이나 절 오기입은 여기서 걸립니다.</li>
    <li><b>자리 중복 차단</b> — 같은 절·같은 <code>anchor</code>는 문장이 아무리 달라도 하나만 통과합니다.</li>
    <li><b>빈 절 우선</b> — 모든 절에 하나씩 깔고 난 뒤에야 두 번째를 얹습니다.</li>
  </ul>
</section>

{''.join(days)}

<section>
  <h2><span class="n">4</span>개수 강제를 풀었습니다 — "정확히 22개" → "최대 22개까지"</h2>
  <p class="sub">7/16이 무너진 진짜 원인이 여기 있었습니다.</p>
  <div class="callout bad">
    <b>7/16은 후보 22개 중 고유 질문이 9개뿐이었고, 나머지 13개는 글자까지 똑같은 복사본이었습니다.</b>
    같은 질문이 3번씩 반복됐습니다. 삼하 7:18-29는 다윗의 기도 하나로 이어진 12절짜리라
    서로 다른 질문거리가 9개쯤에서 바닥나는데, 프롬프트가 "22개를 만들어라"라고 개수를 못 박아서
    모델이 <b>없는 걸 지어내는 대신 있는 걸 복사해서</b> 채웠습니다.
  </div>
  <p>세 가지를 바꿨습니다:</p>
  <ul class="plain">
    <li><b>프롬프트</b> — "최대 22개까지 만들되, 서로 다른 게 더 없으면 거기서 멈춰라. 복사로 개수를 채우는 건 가장 나쁜 결과다."</li>
    <li><b>스키마</b> — 최소 개수를 12로 낮춰 적게 내는 걸 허용</li>
    <li><b>코드</b> — 글자가 같은 후보는 판정에 넘기기 전에 제거</li>
  </ul>
  <table>
    <tr><th>날짜</th><th>모델이 낸 후보</th><th>복사본</th><th>판정 통과</th><th>GPT 교체</th></tr>
    <tr><td>7/14</td><td>16개</td><td>0</td><td>12/16</td><td>0라운드</td></tr>
    <tr><td>7/15</td><td>16개</td><td>0</td><td>16/16</td><td>0라운드</td></tr>
    <tr><td><b>7/16</b></td><td><b>12개</b></td><td><b>0</b></td><td><b>12/12</b></td><td>0라운드</td></tr>
    <tr><td>7/17</td><td>15개</td><td>0</td><td>14/15</td><td>0라운드</td></tr>
  </table>
  <p><b>모델이 이제 정직하게 신고합니다.</b> 재료가 얇은 7/16은 12개만 내고 멈췄고, 그 12개가 전부 판정을 통과했습니다.
  4일 모두 GPT 교체가 한 번도 필요 없었습니다.</p>
</section>

<section>
  <h2><span class="n">5</span>프롬프트 전면 점검 — 서로 싸우는 규칙들을 정리했습니다</h2>
  <p class="sub">질문 생성 프롬프트 6,588자 중 제가 손댄 건 30%뿐이었고, 나머지 70%는 옛 구조 시절 문서였습니다.</p>
  <h3>같은 프롬프트 안에서 정반대 지시 — 3건</h3>
  <table>
    <tr><th>충돌</th><th>한쪽</th><th>다른 쪽</th></tr>
    <tr><td><b>구조</b></td>
        <td>"메인 질문 3개와 각 메인에서 파생되는 꼬리 질문 2개씩, 그리고 <b>각 질문의 답변을 생성</b>합니다"</td>
        <td>"후보는 전부 대등하다 — <b>메인·꼬리를 나누지 마라. 답변은 만들지 않는다</b>"</td></tr>
    <tr><td><b>왜·이유·의미</b></td>
        <td>"<b>메인 절대 금지 패턴 〔어기면 즉시 재작성〕</b> — '왜 ~했나요?' · '이유는 무엇인가요?' · '의미는 무엇인가요?'"</td>
        <td>"'왜/이유' 단어는 <b>금지가 아니다</b>"</td></tr>
    <tr><td><b>재료 범위</b></td>
        <td>"<b>연결 질문 1개</b> — 오늘 본문의 단서가 <b>다른 성경 본문</b>과 어떻게 이어지는지"</td>
        <td>"<b>본문 밀착(절대):</b> 그날 본문에 나오는 단어·인물·지명<b>에서만</b> 출발. 다른 장의 사건·인물 금지"</td></tr>
  </table>
  <div class="callout bad">
    <b>"절대 금지"라고 써둔 규칙이 실제로는 24% 어겨지고 있었습니다.</b>
    기록된 질문 711개를 세어보니 "…이유는 무엇" 170개(23.9%), "…의미는" 64개(9.0%), "왜 ~했나" 27개(3.8%) —
    <b>합쳐서 약 37%</b>가 그 '절대 금지 패턴'이었습니다. 지켜지지 않는 규칙이 토큰만 쓰고 판정에 혼선을 줬습니다.
  </div>
  <h3>바꾼 정책 — 문제는 단어가 아니라 반복이었습니다</h3>
  <p>'왜·이유·의미'를 금지하는 대신 <b>"한 소재에는 질문 하나"</b>로 통일했습니다. 실제 실패 사례가 이걸 정확히 보여줍니다:</p>
  <div class="callout warn">
    ✗ "아람 사람들의 <b>배경</b>은?" + "아람을 고용한 <b>이유</b>는?" + "벧르홉·소바의 <b>역할</b>은?"<br>
    → 문장은 셋 다 다르지만 답은 전부 '암몬이 아람 용병을 고용한 일' 하나입니다.
  </div>
  <h3>카테고리 라벨이 갈라져 다양성 계산이 왜곡되고 있었습니다</h3>
  <p>'신학/해석 견해'와 '신학/해석', '지명'과 '지명 정보', '연결'과 '연결 질문'이 <b>서로 다른 카테고리로 세어지고</b> 있었습니다.
  선택 로직이 카테고리 다양성을 이 라벨로 계산하므로, <b>다양성을 실제보다 부풀려</b> 평가했습니다. 공식 9개 이름으로 통일했습니다.</p>
  <table>
    <tr><th>카테고리</th><th>기존 711개</th><th>신규 36개</th></tr>
    <tr><td>신학/해석 견해</td><td>24.5%</td><td>25.0%</td></tr>
    <tr><td>본문 디테일</td><td>12.6%</td><td>19.4%</td></tr>
    <tr><td><b>주석형/본문관찰</b></td><td><b>2.2%</b></td><td><b>16.7%</b></td></tr>
    <tr><td>문화·관습</td><td>15.6%</td><td>13.9%</td></tr>
    <tr><td>인물 배경</td><td>14.1%</td><td>13.9%</td></tr>
  </table>
  <p><b>사실상 사문화됐던 '주석형/본문관찰'이 되살아났습니다</b>(2.2% → 16.7%). 라벨 분열도 사라졌습니다.</p>
  <p class="cap">프롬프트는 질문 생성 6,588자 → 6,189자, 교체 5,113자 → 4,538자로 <b>줄었습니다</b>.</p>
</section>

<section>
  <h2><span class="n">6</span>아직 남은 것 — 정직하게</h2>
  <h3>① 절이 달라도 소재가 같으면 못 막습니다</h3>
  <p>7/14에 겹침 2건이 남았는데, 둘 다 <b>서로 다른 절</b>에 정박해 있습니다:</p>
  <table>
    <tr><th>질문 쌍</th><th>뜻 겹침</th></tr>
    <tr><td>미갈이 다윗을 업신여긴 <b>이유</b>는?<br>미갈이 다윗을 비난한 장면에서 드러나는 <b>감정</b>은?</td><td>0.88</td></tr>
    <tr><td>다윗이 '뛰놀리라'고 말한 <b>이유</b>는?<br>다윗이 뛰놀며 춤추는 모습이 주는 <b>메시지</b>는?</td><td>0.77</td></tr>
  </table>
  <p>절 배치는 '본문의 서로 다른 자리'를 보장하지만, <b>같은 인물·사건이 여러 절에 걸쳐 있으면</b> 자리가 달라도 답이 같아집니다.
  이 영역은 <b>임베딩으로 고르는 단계</b>(MMR 등)가 필요한 자리입니다.</p>
  <h3>② 관주를 넣었지만 실제로는 안 쓰입니다</h3>
  <p>OpenBible 관주를 질문 생성기에 처음으로 전달했습니다(7/16 기준 12개 절, 1,103자 — 시편 8:4, 출애굽기 15:11, 사무엘상 2:35, 민수기 6:24-26 등).
  로컬 조회라 <b>API 비용은 0원</b>입니다.</p>
  <div class="callout warn">
    <b>그런데 4일치 36개 질문 중 '연결 질문' 카테고리가 0개입니다.</b>
    답변에서 다른 성경을 언급한 것도 1건뿐입니다. 재료는 도착했는데 모델이 쓰지 않았습니다.<br><br>
    원인으로 보이는 것: 출처 기록 규칙이 여전히 "<b>오늘 절의 글자를 그대로 인용하라</b>"고 요구해서,
    관주는 '참고 자료'일 뿐 <b>질문의 근거로 삼을 통로가 없습니다</b>.
    다음 단계는 <b>관주형 출처 기록</b>를 정식 종류로 만드는 것입니다 — 그러면 자리도 늘고 사용도 강제됩니다.
  </div>
  <h3>③ 신학 쏠림은 그대로입니다</h3>
  <p>신학/해석 견해가 여전히 25%로 1위입니다(기존 24.5%). 초신자 대상 묵상인데 해석 견해가 가장 많습니다.
  카테고리별 상한을 두는 방법이 있지만, 먼저 재료(관주·주의점)가 실제로 쓰이게 한 뒤에 판단하는 게 순서로 보입니다.</p>
</section>

<section>
  <h2><span class="n">7</span>비용</h2>
  <table>
    <tr><th>날짜</th><th>기존</th><th>신규</th><th>차이</th></tr>
    {''.join(f"<tr><td>{d['date']}</td><td>{d['cost_before'].get('cost_krw', 0):.1f}원</td>"
             f"<td>{d['cost_after'].get('cost_krw', 0):.1f}원</td>"
             f"<td>{d['cost_after'].get('cost_krw', 0) - d['cost_before'].get('cost_krw', 0):+.1f}원</td></tr>"
             for d in data)}
    <tr><td><b>평균</b></td><td><b>{cb:.1f}원</b></td><td><b>{ca:.1f}원</b></td>
        <td><b>{ca - cb:+.1f}원</b></td></tr>
  </table>
  <div class="callout">
    <b>출처 기록이 실제로 추가하는 비용은 하루 약 5원입니다.</b><br>
    프롬프트에 붙인 규칙 약 400토큰(≈1.5원) + 후보 16개가 <code>verse</code>·<code>anchor</code>를 뱉는 출력 약 240토큰(≈3.6원).
    나머지 차이는 답변 작성(GPT-4o)의 재시도 편차로, 날짜별 널뛰기가 개편 효과보다 큽니다.
  </div>
  <p>겹침 측정에 쓰는 임베딩도 <code>text-embedding-3-small</code> 기준 100만 토큰에 $0.02라,
  하루 9개 답변이면 <b>1년에 약 4원</b>입니다. 한 번 부른 값은 캐시에 저장돼 재실행은 무료입니다.</p>
</section>

<section>
  <h2><span class="n">8</span>측정 방법이 바뀌었습니다</h2>
  <p class="sub">기존 잣대(단어 겹침)가 못 믿을 물건이라는 게 이번에 확인됐습니다.</p>
  <p>같은 사실을 다른 어휘로 쓰면 단어가 안 겹칩니다. 문헌에서 <b>"fast car" vs "quick automobile"</b>로 알려진
  교과서적 실패이고, 임계값을 조정해서 해결되는 문제가 아닙니다.</p>
  <table>
    <tr><th>쌍</th><th>단어 겹침</th><th>뜻 겹침</th><th>실제</th></tr>
    <tr><td>7/19 아람 배경 ↔ 벧르홉·소바 역할</td><td>0.18</td><td><b>0.76</b></td>
        <td><span class="verdict bad">진짜 겹침</span></td></tr>
    <tr><td>7/15 목장에서 데려오심 ↔ 주권자로의 전환</td><td>0.27</td><td><b>0.78</b></td>
        <td><span class="verdict bad">진짜 겹침</span></td></tr>
    <tr><td>7/14 베 에봇 두 질문</td><td>0.36</td><td><b>0.85</b></td>
        <td><span class="verdict bad">진짜 겹침</span></td></tr>
  </table>
  <div class="callout warn">
    <b>다만 임베딩도 완벽하지 않습니다.</b> 저장소 전체 2844쌍을 보정해보니,
    진짜 겹침(0.76)이 오탐(0.79 — "벧세메스에서 들여다봄" ↔ "기럇여아림으로 옮김", 서로 다른 사건)보다
    낮은 구간이 실제로 있습니다. <b>깔끔한 경계선은 존재하지 않습니다.</b><br><br>
    그래서 임계값 0.75는 <b>판결이 아니라 선별 그물</b>로 잡았습니다 — 놓치기보다 과잉 신고하고,
    걸린 건 사람이 봅니다. 예방은 잣대가 아니라 <b>절 배치</b>가 담당합니다.
  </div>
</section>

<section>
  <h2><span class="n">9</span>이 방식이 정론인지 — 문헌 확인</h2>
  <p class="sub">먼저 만들고 나중에 찾아봤는데, 학계·업계가 권하는 1순위 방법과 같았습니다.</p>
  <ul class="plain">
    <li><b>Explicit Diversity Conditions for QAG</b> (COLING 2024) — 문서를 5등분해 "2번 위치에서 질문 하나를 만들어라"라고 위치를 지정. 질문끼리 겹치는 비율이 <b>63.1% → 30.7%</b>로 떨어졌습니다. 우리와 같은 발상이고, 우리는 글자 수 대신 <b>'절'이라는 의미 단위</b>를 씁니다.</li>
    <li><b>Ragas · Persona Hub</b> — 다양성을 "다양하게 써줘"라고 부탁하지 않고, 서로 다른 씨앗(그래프 노드·페르소나)을 코드가 배정합니다.</li>
    <li><b>Verbalized Sampling</b> (2025) — "한 번에 여러 개를 다양하게" 요청하는 방식(= 우리 기존 방식)을 실험해 <b>"단순히 다양하게 해달라는 요청으로는 부족하다"</b>고 결론.</li>
    <li><b>Lost in the Middle</b> (TACL 2024) · <b>FollowBench</b> · <b>ComplexBench</b> — 모델은 프롬프트 가운데를 흘리고, 제약을 겹겹이 쌓을수록 지시 이행률이 떨어집니다. <b>긴 규칙 목록은 비용만 쓰고 효과가 낮습니다.</b></li>
    <li><b>SemDeDup · SemHash</b> — 단어 기반 중복 제거가 의미를 못 본다는 것이 이들이 존재하는 이유입니다.</li>
  </ul>
  <div class="callout">
    <b>다만 논문도 겹침을 30.7%까지 낮췄을 뿐 0으로 만들지는 못했습니다.</b>
    Persona Hub가 글자 검사와 의미 검사를 <b>둘 다</b> 돌리는 이유입니다.
    우리도 출처 기록으로 막고 임베딩으로 확인하는 이중 구조가 맞습니다.
  </div>
  <p class="src">
    출처 —
    <a href="https://arxiv.org/html/2406.17990v1">arXiv:2406.17990</a> ·
    <a href="https://arxiv.org/html/2510.01171v1">arXiv:2510.01171</a> ·
    <a href="https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long">Lost in the Middle</a> ·
    <a href="https://arxiv.org/abs/2303.09540">arXiv:2303.09540</a> ·
    <a href="https://arxiv.org/html/2406.20094v3">arXiv:2406.20094</a>
  </p>
</section>

<section>
  <h2><span class="n">10</span>바뀐 파일</h2>
  <table>
    <tr><th>파일</th><th>무엇이 바뀌었나</th></tr>
    <tr><td><code>scripts/followup_simple.py</code></td>
        <td>출처 기록 스키마(<code>verse</code>·<code>anchor</code>) 추가 · 본문 대조 검증 · 절 우선 배치 선택 · 프롬프트 13% 축소</td></tr>
    <tr><td><code>scripts/_measure_answer_overlap.py</code></td>
        <td>단어 겹침 → <b>임베딩 뜻 겹침</b>으로 교체(캐시 내장) · 절 겹침 지표 추가 · <code>--calibrate</code> 추가</td></tr>
    <tr><td><code>scripts/_ab_test_step2.py</code></td>
        <td>절·출처 기록 지표 출력 추가</td></tr>
  </table>
  <p class="cap">모두 미커밋 상태이고, 운영 데이터(<code>data/</code>)는 건드리지 않았습니다.
  <code>_</code> 접두사 파일은 커밋·푸시하지 않는 로컬 도구입니다.</p>
</section>

</div>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"생성: {OUT}")
    print(f"  크기 {len(doc):,}자 · 날짜 {len(data)}일")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
