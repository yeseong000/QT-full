# -*- coding: utf-8 -*-
"""프롬프트 개선 전/후 비교 리포트 — 사장님이 직접 판단하실 자료.
새 생성 없음 · 임베딩 캐시만(API 0).
"""
import sys, json, re, html, itertools
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent   # repo 루트
SP = EXP.parent               # 비교 스냅샷(before_0804 등)이 있는 폴더
sys.path.insert(0, str(EXP / "scripts"))
import followup_simple as fs
import _measure_answer_overlap as mao

CACHE = json.load(open(EXP / "scripts" / "_embed_cache.json", encoding="utf-8"))
DATES = ["2026-07-31", "2026-08-01", "2026-08-02", "2026-08-03"]
VERS = [("전", SP / "before_0804", "지금 운영 중인 옛 엔진 결과"),
        ("v1", SP / "after_v1_0804", "카테고리 규칙 첫 투입 (나쁜 예시를 문장 그대로 넣음)"),
        ("v2", SP / "after_v2_0804", "나쁜 예시를 빼고 패턴으로만 기술"),
        ("v3", EXP / "data" / "deep_dive", "‘대상은 따옴표 인용구여야 한다’ 요건 추가")]
BAN = ["영향", "메시지", "교훈", "의의"]
QUOTE = re.compile(r"['\"‘’“”][^'\"‘’“”]{1,40}['\"‘’“”]")
e = html.escape


def cached(ts):
    if any(mao._key(t) not in CACHE for t in ts):
        return None
    return [CACHE[mao._key(t)] for t in ts]


def load(base, d):
    j = json.load(open(Path(base) / f"{d}.json", encoding="utf-8"))
    meta = j.get("_followup_meta") or {}
    cm = {c["question"]: c for c in (meta.get("candidates") or [])}
    catm = {c.get("question"): c.get("category") for c in (meta.get("category_map") or [])}
    ns = []
    for it in j.get("follow_up_questions") or []:
        for k, q in enumerate([it] + list(it.get("follow_ups") or [])):
            c = cm.get(q["question"], {})
            ns.append({"q": q["question"], "a": q.get("answer", ""), "main": k == 0,
                       "cat": fs._canon_cat(c.get("category") or catm.get(q["question"]) or "") or "—",
                       "atype": c.get("anchor_type"), "anchor": c.get("anchor"),
                       "ok": c.get("anchor_ok")})
    v = cached([x["a"] for x in ns]) if ns and all(x["a"] for x in ns) else None
    dupi = set()
    if v:
        for i, k in itertools.combinations(range(len(ns)), 2):
            if mao.cosine(v[i], v[k]) >= 0.75:
                dupi.add(i); dupi.add(k)
    for i, x in enumerate(ns):
        x["dup"] = i in dupi
        x["ban"] = [w for w in BAN if w in x["q"]]
        x["quote"] = bool(QUOTE.search(x["q"]))
    g = meta.get("embed_gate") or {}
    return {"ref": j.get("scripture_ref", ""), "nodes": ns,
            "cost": (j.get("_cost_followup") or {}).get("cost_krw"),
            "cut": g.get("dropped_by_embed"), "ns": len(ns)}


DATA = {v: {d: load(b, d) for d in DATES} for v, b, _ in VERS}

# ── KB 재료: 주의점/신학_핵심에 인용구가 있는지 ──
kb = json.load(open(EXP / "data" / "reference" / "사무엘하.json", encoding="utf-8"))
MAT = []
for ch in ("14", "15"):
    body = kb.get(ch) or {}
    for i, w in enumerate((body.get("주의점") or []), 1):
        MAT.append({"id": f"{ch}:주의점#{i}", "text": w, "quote": bool(QUOTE.search(w))})
    if body.get("신학_핵심"):
        MAT.append({"id": f"{ch}:신학_핵심#1", "text": body["신학_핵심"],
                    "quote": bool(QUOTE.search(body["신학_핵심"]))})

TARGET = "신학/해석 견해"


def stat(ver):
    hs = [x for d in DATES for x in DATA[ver][d]["nodes"] if x["cat"] == TARGET]
    return {"n": len(hs),
            "kb": sum(1 for x in hs if x["atype"] == "KB" and x["ok"]),
            "ban": sum(1 for x in hs if x["ban"]),
            "quote": sum(1 for x in hs if x["quote"]),
            "total": sum(DATA[ver][d]["ns"] for d in DATES),
            "dup": sum(1 for d in DATES for x in DATA[ver][d]["nodes"] if x["dup"])}


S = {v: stat(v) for v, _, _ in VERS}


def qcard(x):
    tags = []
    if x["cat"] == TARGET:
        tags.append("<span class='t t--focus'>신학/해석 견해</span>")
    if x["atype"] == "KB" and x["ok"]:
        tags.append(f"<span class='t t--kb'>{e(str(x['anchor']))}</span>")
    elif x["cat"] == TARGET:
        tags.append("<span class='t t--none'>근거 표기 없음</span>")
    if x["quote"]:
        tags.append("<span class='t t--ok'>인용구</span>")
    if x["ban"]:
        tags.append(f"<span class='t t--ban'>{e('·'.join(x['ban']))}</span>")
    if x["dup"]:
        tags.append("<span class='t t--dup'>답 겹침</span>")
    cls = "q" + (" q--focus" if x["cat"] == TARGET else "") + (" q--dup" if x["dup"] else "")
    return (f"<div class='{cls}'><p class='qt'>{e(x['q'])}</p>"
            f"<p class='qc'>{e(x['cat'])}</p><div class='tags'>{''.join(tags)}</div></div>")


rows = []
for d in DATES:
    cols = []
    for v, _, _ in VERS:
        D = DATA[v][d]
        cols.append(f"<div class='col'><h3>{v}<span>{D['ns']}개"
                    + (f" · {D['cost']:.0f}원" if D['cost'] else "")
                    + (f" · 관문 {D['cut']}개 뺌" if D['cut'] else "") + "</span></h3>"
                    + "".join(qcard(x) for x in D["nodes"]) + "</div>")
    rows.append(f"<section class='day'><h2>{e(d)} · {e(DATA['v3'][d]['ref'])}</h2>"
                f"<div class='grid'>{''.join(cols)}</div></section>")

# 재료 ↔ 그 재료로 실제 만들어진 질문 (모든 버전에서 수집)
made = {}
for v, _, _ in VERS:
    for d in DATES:
        for x in DATA[v][d]["nodes"]:
            if x["atype"] == "KB" and x["ok"] and x["anchor"]:
                made.setdefault(str(x["anchor"]), set()).add((x["q"], bool(x["ban"])))

matrows = ""
for m in MAT:
    qs = sorted(made.get(m["id"], []))
    if qs:
        qhtml = "".join(
            f"<p class='mq {'mq--bad' if bad else 'mq--good'}'>→ {e(q)}"
            + (" <span class='t t--ban'>추상어</span>" if bad else "") + "</p>"
            for q, bad in qs)
        cls = "no" if any(b for _, b in qs) else "has"
        mark = "덩어리 질문 나옴" if any(b for _, b in qs) else "구체적 질문 나옴"
    else:
        qhtml, cls, mark = "<p class='mq mq--none'>아직 안 쓰인 재료</p>", "", "—"
    matrows += (f"<tr class='{cls}'><td><code>{e(m['id'])}</code></td><td>{mark}</td>"
                f"<td>{e(m['text'].split('(근거')[0].strip()[:130])}{qhtml}</td></tr>")
nq = sum(1 for m in MAT if made.get(m["id"]))

CSS = """
:root{--bg:#f5f5f7;--card:#fff;--txt:#1d1d1f;--dim:#6e6e73;--line:rgba(0,0,0,.09);
--red:#d70015;--redbg:rgba(215,0,21,.10);--grn:#0f7b3f;--grnbg:rgba(48,209,88,.18);
--blu:#0071e3;--blubg:rgba(0,113,227,.12);--amb:#9a6400;--ambbg:rgba(255,159,10,.16);
--sh:0 1px 2px rgba(0,0,0,.04),0 10px 30px -12px rgba(0,0,0,.14)}
@media(prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--txt:#f5f5f7;--dim:#98989d;
--line:rgba(255,255,255,.12);--red:#ff453a;--redbg:rgba(255,69,58,.18);--grn:#30d158;
--grnbg:rgba(48,209,88,.20);--blu:#0a84ff;--blubg:rgba(10,132,255,.20);--amb:#ffd60a;
--ambbg:rgba(255,214,10,.16);--sh:0 1px 2px rgba(0,0,0,.5),0 10px 30px -12px rgba(0,0,0,.8)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);padding:0 20px 100px;
font:16px/1.65 -apple-system,BlinkMacSystemFont,"Pretendard","Apple SD Gothic Neo","Segoe UI",sans-serif;
-webkit-font-smoothing:antialiased}
.wrap{max-width:1400px;margin:0 auto}
h1{font-size:34px;letter-spacing:-.022em;margin:56px 0 8px}
.lead{color:var(--dim);font-size:17px;margin:0 0 32px;max-width:760px}
.card{background:var(--card);border-radius:18px;padding:24px 26px;box-shadow:var(--sh);margin-bottom:16px}
.card h2{font-size:20px;margin:0 0 14px;letter-spacing:-.012em}
table{width:100%;border-collapse:collapse;font-size:14.5px}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr.has td:nth-child(2){color:var(--grn);font-weight:600}
tr.no td:nth-child(2){color:var(--red);font-weight:600}
code{font-size:13px;background:var(--line);padding:2px 6px;border-radius:5px}
.tblwrap{overflow-x:auto}
.day{background:var(--card);border-radius:18px;padding:20px 22px;box-shadow:var(--sh);margin-bottom:16px}
.day h2{font-size:18px;margin:0 0 14px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:1100px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:640px){.grid{grid-template-columns:1fr}}
.col h3{font-size:13px;margin:0 0 10px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
.col h3 span{display:block;text-transform:none;letter-spacing:0;font-weight:400;font-size:12px;margin-top:2px}
.q{background:var(--bg);border-radius:11px;padding:10px 12px;margin-bottom:8px}
.q--focus{box-shadow:inset 3px 0 0 var(--blu)}
.q--dup{opacity:.55}
.qt{margin:0 0 5px;font-size:14px;line-height:1.45}
.qc{margin:0 0 6px;font-size:11.5px;color:var(--dim)}
.tags{display:flex;flex-wrap:wrap;gap:4px}
.t{font-size:10.5px;font-weight:600;padding:2px 7px;border-radius:999px;white-space:nowrap}
.t--focus{background:var(--blubg);color:var(--blu)}
.t--kb{background:var(--grnbg);color:var(--grn)}
.t--none{background:var(--redbg);color:var(--red)}
.t--ok{background:var(--grnbg);color:var(--grn)}
.t--ban{background:var(--redbg);color:var(--red)}
.t--dup{background:var(--ambbg);color:var(--amb)}
.big{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:18px 0 4px}
.big div{background:var(--bg);border-radius:13px;padding:14px 16px}
.big b{display:block;font-size:26px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.big span{font-size:12.5px;color:var(--dim)}
.ba{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media(max-width:760px){.ba{grid-template-columns:1fr}}
.ba>div{border-radius:13px;padding:14px 16px}
.ba .bad{background:var(--redbg)}
.ba .good{background:var(--grnbg)}
.ba h4{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em}
.ba .bad h4{color:var(--red)} .ba .good h4{color:var(--grn)}
.ba p{margin:0 0 6px;font-size:14px}
.mq{margin:6px 0 0;font-size:13.5px;padding-left:10px}
.mq--good{color:var(--grn)}.mq--bad{color:var(--red)}.mq--none{color:var(--dim);font-style:italic}
tr.has td:nth-child(2){color:var(--grn);font-weight:600}
tr.no td:nth-child(2){color:var(--red);font-weight:600}
.ba small{color:var(--dim);font-size:12.5px;display:block;margin-bottom:10px}
.note{color:var(--dim);font-size:14.5px}
"""

doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>떠오르는 질문 · 프롬프트 개선 전후 비교</title><style>{CSS}</style></head><body><div class="wrap">
<h1>프롬프트 개선, 무엇이 되고 무엇이 안 됐나</h1>
<p class="lead">‘신학/해석 견해’ 카테고리 하나를 상세 규칙으로 고쳐 4일(7/31~8/03)을 세 번 다시 생성했습니다.
아래는 그 전수입니다. 제 판단이 틀렸을 수 있으니 직접 보시고 정해 주세요.</p>

<div class="card">
  <h2>한눈에</h2>
  <div class="tblwrap"><table>
    <tr><th>버전</th><th>무엇을 바꿨나</th><th class="n">이 카테고리 질문</th><th class="n">근거 표기</th>
    <th class="n">금지어</th><th class="n">인용구 대상</th><th class="n">전체 질문</th><th class="n">답 겹침</th></tr>
    {''.join(f'<tr><td><b>{v}</b></td><td class="note">{e(desc)}</td>'
             f'<td class="n">{S[v]["n"]}</td><td class="n">{S[v]["kb"]}</td>'
             f'<td class="n">{S[v]["ban"]}</td><td class="n">{S[v]["quote"]}</td>'
             f'<td class="n">{S[v]["total"]}</td><td class="n">{S[v]["dup"]}</td></tr>'
             for v, _, desc in VERS)}
  </table></div>
  <div class="big">
    <div><b style="color:var(--grn)">0 → {S['v3']['kb']}</b><span>근거 표기 (성공)</span></div>
    <div><b style="color:var(--red)">{S['전']['ban']} → {S['v3']['ban']}</b><span>금지어 (실패)</span></div>
    <div><b>{S['v2']['n']} = {S['v3']['n']}</b><span>v2와 v3가 동일</span></div>
  </div>
  <p class="note" style="margin-top:14px">
  <b>성공한 것</b> — 이 카테고리 질문이 이제 <b>어느 주석가의 어느 견해에서 나왔는지</b>를 실제로 지목합니다.
  전에는 0개, 지금은 전부입니다. 지어낸 견해는 코드가 대조해 걸러냅니다.<br>
  <b>실패한 것</b> — 추상적인 말(영향·메시지·교훈·의의)이 안 줄었습니다. 세 가지 방식으로 시도했는데
  <b>v3는 v2와 결과가 똑같이 나왔습니다.</b> 프롬프트로 더 설득하는 건 한계로 보입니다.</p>
</div>

<div class="card">
  <h2>왜 안 되는가 — 재료가 무엇을 짚느냐가 갈랐습니다</h2>
  <div class="ba">
    <div class="good"><h4>재료가 본문의 한 표현을 짚을 때</h4>
      <small>15:주의점#2 — “압살롬이 <b>백성의 마음을 훔쳤다는 표현</b>은 문자적으로 해석하기보다는…”<br>재료가 본문의 <b>한 표현</b>을 지목합니다(따옴표는 없습니다).</small>
      <p>→ “<b>‘백성의 마음을 훔쳤다’</b>는 표현을 학자들은 어떻게 읽나요?”</p>
      <small>대상이 본문의 한 표현이라 답이 그 표현에만 붙습니다.</small></div>
    <div class="bad"><h4>재료가 장면 전체를 짚을 때</h4>
      <small>14:주의점#4 — “드고아 여인의 <b>간청</b>은 하나님의 자비를 강조하지만, 이는 요압의 계획에 따른 것…”<br>재료가 <b>장면 하나를 통째로</b> 가리킵니다.</small>
      <p>→ “상주로 가장한 드고아 여인의 <b>이야기가 주는 메시지</b>는 무엇인가요?”</p>
      <small>재료가 장면 전체를 다루니 질문도 장면 전체가 됩니다. 답이 그날 줄거리 요약이 되어 다른 질문과 겹칩니다.</small></div>
  </div>
  <p class="note" style="margin-top:14px">따옴표는 <b>모델이 질문을 쓰면서 붙인 것</b>이지 재료에 있던 게 아닙니다.
  그래서 프롬프트에 “따옴표로 인용한 표현을 대상으로 삼아라”라고 요건을 걸어도(v3), 재료가 장면을 가리키면
  <b>인용할 말 자체가 없어</b> 소용이 없습니다. 모델을 더 다그쳐도 안 되는 이유입니다.</p>
</div>

<div class="card">
  <h2>제가 세운 개선안 하나는 이미 틀렸습니다</h2>
  <p class="note">저는 “재료에 따옴표로 인용된 표현이 있는 것만 쓰자”고 제안하려 했는데,
  실제로 KB 재료 <b>{len(MAT)}개를 열어 보니 따옴표가 들어 있는 것은 0개</b>였습니다.
  좋은 질문에 붙어 있던 따옴표는 재료에 있던 게 아니라 <b>모델이 질문을 쓰면서 붙인 것</b>이었습니다.
  그래서 그 필터는 성립하지 않습니다.</p>
  <p class="note">대신 재료 전부와, 그 재료로 실제 나온 질문을 아래에 폈습니다.
  <b>어떤 재료가 쓸 만하고 어떤 재료가 덩어리 질문을 부르는지</b> 직접 봐 주십시오.
  사장님이 갈라 주시면 그 기준을 코드에 넣겠습니다.</p>
  <div class="tblwrap"><table>
    <tr><th>재료 번호</th><th>결과</th><th>재료 내용 · 이 재료로 나온 질문</th></tr>{matrows}
  </table></div>
  <p class="note" style="margin-top:14px">
  눈에 띄는 차이 하나는 있습니다 — 재료가 <b>본문의 한 표현·한 판결</b>을 짚으면
  (‘백성의 마음을 훔쳤다는 표현’, ‘법적 절차를 무시’) 구체적 질문이 나오고,
  <b>장면 전체</b>를 짚으면(‘드고아 여인의 간청’, ‘압살롬의 귀환’) 덩어리 질문이 나옵니다.
  다만 이걸 코드가 자동으로 가려낼 규칙은 아직 못 찾았습니다.</p>
</div>

<div class="card">
  <h2>지금 확실한 개선은 하나뿐입니다</h2>
  <p class="note"><b>추상어 4개(영향·메시지·교훈·의의)를 코드에서 막는 것.</b>
  프롬프트로 세 번(v1·v2·v3) 부탁했지만 한 번도 안 지켜졌습니다.
  코드로 막으면 그 질문은 자동으로 교체 대상이 되어, 후보 창고에서 다른 질문으로 갈아끼워집니다
  (이미 그렇게 도는 자리가 있습니다).</p>
  <p class="note"><b>바뀌는 모습</b> — 4일 기준 <b>{S['v3']['ban']}개</b>가 걸러지고 다른 각도의 질문으로 대체됩니다.
  다만 걱정되는 점도 말씀드립니다: <code>14:주의점#8</code>처럼
  <b>근거는 제대로 댔는데 표현만 추상적인 질문</b>도 함께 버려집니다.
  버리는 대신 ‘표현만 고쳐 쓰게’ 할 수도 있는데, 그건 GPT를 한 번 더 부르는 비용이 듭니다.</p>
</div>

<h1 style="font-size:26px;margin-top:44px">날짜별 전수 — 직접 보시고 판단해 주세요</h1>
<p class="lead">파란 줄이 ‘신학/해석 견해’입니다. 흐리게 표시된 건 답이 다른 질문과 겹쳐 관문이 잘라낸 것입니다.</p>
{''.join(rows)}
</div></body></html>"""

out = Path(sys.argv[1]) if len(sys.argv) > 1 else SP / "프롬프트_전후비교.html"
out.write_text(doc, encoding="utf-8")
print(f"저장: {out}")
for v, _, _ in VERS:
    print(f"  {v}: 카테고리 {S[v]['n']}개 · 근거 {S[v]['kb']} · 금지어 {S[v]['ban']} · 인용구 {S[v]['quote']} · 전체 {S[v]['total']} · 겹침 {S[v]['dup']}")
print(f"  재료 {len(MAT)}개 중 인용구 있는 것 {nq}개")
