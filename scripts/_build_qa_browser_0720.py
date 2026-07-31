"""떠오르는 질문 — 전체 질문·답변 브라우저 HTML. ※ 로컬 도구(_접두사).

사장님 요청(2026-07-20): "다른 날짜의 질문 답변들도 어떻게 바뀌었는지 체크할 수 있게"

4일 × (기존 1 + 신규 3회차) = 총 144개 질문·답변을 전부 담는다.
질문마다 출처 기록(몇 절·어느 표현)·카테고리·중복 여부를 붙여 눈으로 대조할 수 있게 한다.

사용: python scripts/_build_qa_browser_0720.py
"""
import glob
import html
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _measure_answer_overlap as mo  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = Path(r"C:\Users\USER\Desktop\앱 개발\7.주만나 큐티\떠오르는질문_전체보기_0720.html")
DATES = ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]
SAFE = ("인물 배경", "문화·관습", "어원·유래", "지명 정보")


def esc(s):
    return html.escape(str(s if s is not None else ""))


def dup_index(r):
    idx = {}
    for p in r["sim_flagged"]:
        for k, other in ((p["i"], p["j"]), (p["j"], p["i"])):
            idx.setdefault(k, []).append((p["sim"], r["qs"][other]["question"]))
    return idx


def qa_block(r, meta=None, show_src=True):
    """질문 9개 — 클릭하면 답변. 중복은 빨간 테두리."""
    idx = dup_index(r)
    info = {}
    if meta:
        for c in meta.get("candidates") or []:
            if c.get("selected"):
                info[c["question"]] = c
    out = []
    for i, q in enumerate(r["qs"]):
        dup = idx.get(i, [])
        c = info.get(q["question"], {})
        cat = c.get("category", "")
        tags = ""
        if cat:
            safe = " safe" if cat in SAFE else ""
            tags += f'<span class="tag cat{safe}">{esc(cat)}</span>'
        if show_src and c.get("verse") is not None:
            at = c.get("anchor_type", "본문")
            tags += (f'<span class="tag src">{esc(c["verse"])}절'
                     f'{" · 관주" if at == "관주" else ""} · {esc(str(c.get("anchor", ""))[:12])}</span>')
        if c.get("from_qfix"):
            tags += '<span class="tag fix">교체됨</span>'
        if dup:
            tags += f'<span class="tag dup">중복 {max(s for s, _ in dup):.2f}</span>'
        note = ""
        if dup:
            li = "".join(f"<li>{esc(t)}</li>" for _, t in dup)
            note = f'<div class="dupnote">이 질문과 답이 겹칩니다:<ul>{li}</ul></div>'
        out.append(
            f'<details class="q{" isdup" if dup else ""}">'
            f'<summary><span class="num">{i + 1}</span>'
            f'<span class="qt">{esc(q["question"])}</span>{tags}</summary>'
            f'<div class="ans">{esc(q["answer"]) or "(답변 없음)"}</div>{note}</details>')
    return "".join(out)


def main():
    blocks, nav = [], []
    grand = {"before": 0, "after": 0, "runs": 0, "zero": 0}

    for d in DATES:
        qt = json.loads((REPO / "data" / "qt" / f"{d}.json").read_text(encoding="utf-8"))
        prod = json.loads((REPO / "data" / "deep_dive" / f"{d}.json").read_text(encoding="utf-8"))
        b = mo.analyze(d)
        nb = len(b["sim_flagged"])
        grand["before"] += nb

        panes = [f'<div class="pane"><h3>기존 (운영) '
                 f'<span class="cnt {"bad" if nb else "good"}">중복 {nb}건</span></h3>'
                 f'{qa_block(b, prod.get("_followup_meta"), show_src=False)}</div>']

        for i, f in enumerate(sorted(glob.glob(str(REPO / "scripts" / "_repeat" / f"{d}_r*.json"))), 1):
            j = json.loads(Path(f).read_text(encoding="utf-8"))
            r = mo.analyze(f)
            n = len(r["sim_flagged"])
            grand["after"] += n
            grand["runs"] += 1
            grand["zero"] += (n == 0)
            cats = Counter(c["category"] for c in j["meta"]["candidates"] if c.get("selected"))
            safe_n = sum(cats[k] for k in SAFE)
            panes.append(
                f'<div class="pane"><h3>신규 {i}회차 '
                f'<span class="cnt {"bad" if n else "good"}">중복 {n}건</span> '
                f'<span class="cnt sub">배경지식 {safe_n}/9 · {j["cost"]["cost_krw"]:.0f}원</span></h3>'
                f'{qa_block(r, j["meta"])}</div>')

        nav.append(f'<a href="#d{d}">{d[5:]}</a>')
        blocks.append(
            f'<section id="d{d}"><h2>{d[5:]} <span class="ref">{esc(qt.get("scripture_ref", ""))}</span></h2>'
            f'<p class="sub">기존 1개 + 신규 3회차. 질문을 누르면 답변이 펼쳐집니다. '
            f'빨간 테두리 = 답이 겹치는 질문.</p>'
            f'<div class="panes">{"".join(panes)}</div></section>')

    CSS = """
*{box-sizing:border-box}body{margin:0;background:#f5f5f7;color:#1d1d1f;line-height:1.6;
font-family:-apple-system,BlinkMacSystemFont,'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:0 18px 70px}
header{text-align:center;padding:44px 18px 20px}
h1{font-size:28px;margin:0 0 6px;letter-spacing:-.02em}
header p{margin:0;color:#6e6e73;font-size:15px}
nav{position:sticky;top:0;z-index:9;background:rgba(245,245,247,.85);backdrop-filter:blur(12px);
padding:10px;text-align:center;border-bottom:1px solid rgba(0,0,0,.06);margin-bottom:8px}
nav a{display:inline-block;margin:0 5px;padding:5px 14px;border-radius:999px;background:#fff;
color:#0071e3;text-decoration:none;font-size:13px;font-weight:600;box-shadow:0 1px 2px rgba(0,0,0,.06)}
nav a:hover{background:#0071e3;color:#fff}
nav label{margin-left:14px;font-size:13px;color:#6e6e73;cursor:pointer}
section{background:#fff;border-radius:18px;padding:22px 24px;margin:16px 0;
box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 20px rgba(0,0,0,.05)}
h2{font-size:21px;margin:0 0 4px;letter-spacing:-.01em}
h2 .ref{font-size:14px;color:#86868b;font-weight:400;margin-left:6px}
.sub{color:#6e6e73;font-size:13px;margin:0 0 16px}
.panes{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:1050px){.panes{grid-template-columns:repeat(2,1fr)}}
@media(max-width:640px){.panes{grid-template-columns:1fr}}
.pane h3{font-size:13px;margin:0 0 8px;padding-bottom:7px;border-bottom:1px solid #ececf0;color:#6e6e73}
.cnt{float:right;font-size:11px;padding:1px 8px;border-radius:999px;font-weight:600}
.cnt.good{background:rgba(52,199,89,.15);color:#248a3d}
.cnt.bad{background:rgba(255,59,48,.13);color:#c9251c}
.cnt.sub{background:#f0f0f3;color:#6e6e73;float:none;display:block;margin-top:4px;text-align:right}
details.q{border:1px solid #ececf0;border-radius:10px;margin-bottom:6px;background:#fff;overflow:hidden}
details.q.isdup{border-color:rgba(255,59,48,.4);background:#fffafa}
details.q summary{cursor:pointer;padding:8px 10px;font-size:12.5px;list-style:none;display:flex;
flex-wrap:wrap;gap:5px;align-items:flex-start}
details.q summary::-webkit-details-marker{display:none}
details.q summary:hover{background:rgba(0,0,0,.02)}
.num{flex:0 0 17px;height:17px;border-radius:50%;background:#f0f0f3;color:#86868b;font-size:10px;
display:flex;align-items:center;justify-content:center;margin-top:2px;font-weight:600}
.qt{flex:1 1 100%;min-width:0}
.tag{font-size:10px;padding:1px 7px;border-radius:5px;font-weight:600;white-space:nowrap}
.tag.cat{background:#f0f0f3;color:#6e6e73}
.tag.cat.safe{background:rgba(52,199,89,.14);color:#248a3d}
.tag.src{background:rgba(0,113,227,.1);color:#0071e3}
.tag.fix{background:rgba(255,159,10,.18);color:#a85f00}
.tag.dup{background:rgba(255,59,48,.13);color:#c9251c}
.ans{padding:2px 11px 11px 11px;font-size:12.5px;color:#3a3a3c;white-space:pre-wrap}
.dupnote{margin:0 11px 10px;padding:8px 10px;background:rgba(255,59,48,.06);border-radius:8px;
font-size:11.5px;color:#c9251c}
.dupnote ul{margin:4px 0 0;padding-left:15px}
#dupOnly:checked ~ .wrap details.q:not(.isdup){display:none}
@media(prefers-color-scheme:dark){
body{background:#000;color:#f5f5f7}header p,.sub,.pane h3{color:#98989d}
nav{background:rgba(0,0,0,.8);border-color:rgba(255,255,255,.08)}
nav a{background:#1c1c1e}
section{background:#1c1c1e;box-shadow:0 1px 2px rgba(0,0,0,.5)}
details.q{background:#2c2c2e;border-color:#38383a}
details.q.isdup{background:#2a1416;border-color:rgba(255,69,58,.45)}
details.q summary:hover{background:rgba(255,255,255,.04)}
.pane h3{border-color:#38383a}.num{background:#3a3a3c;color:#98989d}
.tag.cat{background:#3a3a3c;color:#c7c7cc}.cnt.sub{background:#2c2c2e;color:#98989d}
.ans{color:#d1d1d6}}
"""
    JS = """
document.getElementById('expand').addEventListener('click',function(){
  var open=this.dataset.on!=='1';
  document.querySelectorAll('details.q').forEach(function(d){d.open=open});
  this.dataset.on=open?'1':'0';
  this.textContent=open?'전부 접기':'전부 펼치기';
});
"""
    z = grand["zero"]
    doc = f"""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>떠오르는 질문 전체 보기</title><style>{CSS}</style>
<input type="checkbox" id="dupOnly" hidden>
<header>
  <h1>떠오르는 질문 — 전체 보기</h1>
  <p>4일 × (기존 1 + 신규 3회차) · 질문 {grand["runs"] * 9 + len(DATES) * 9}개 전부</p>
  <p style="margin-top:6px;font-size:14px">
    기존 중복 <b>{grand["before"]}건</b> → 신규 12회 합계 <b>{grand["after"]}건</b>
    · 중복 0건 회차 <b>{z}/{grand["runs"]}</b>
  </p>
</header>
<nav>
  {"".join(nav)}
  <label for="dupOnly">중복만 보기</label>
  <a href="#" id="expand" data-on="0" style="cursor:pointer">전부 펼치기</a>
</nav>
<div class="wrap">
{"".join(blocks)}
<section>
  <h2>보는 법</h2>
  <p class="sub">질문 옆 태그의 뜻</p>
  <p><span class="tag cat safe">인물 배경</span> 배경지식 계열 — 낯선 인물·사물·지명·낱말의 정체를 알려주는 질문(중복이 가장 적음)<br><br>
  <span class="tag cat">신학/해석 견해</span> 그 밖의 카테고리<br><br>
  <span class="tag src">18절 · 여호와 앞에</span> 출처 기록 — 이 질문이 본문 몇 절, 어느 표현에서 나왔는지. 코드가 본문과 대조해 검증한 값이라 지어낼 수 없습니다<br><br>
  <span class="tag src">18절 · 관주 · 시편 8:4</span> 관주형 — 그 절과 이어지는 다른 성경 구절에서 나온 질문<br><br>
  <span class="tag fix">교체됨</span> 판정에 걸려 새로 쓴 질문<br><br>
  <span class="tag dup">중복 0.82</span> 다른 질문과 답이 겹침(숫자는 유사도, 0.75 이상이면 표시)</p>
</section>
</div>
<script>{JS}</script>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"생성: {OUT}\n  {len(doc):,}자 · 질문 {grand['runs'] * 9 + len(DATES) * 9}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
