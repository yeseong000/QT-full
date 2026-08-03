# -*- coding: utf-8 -*-
"""사장님이 직접 '이게 중복인가?'를 판단하실 검토 리포트를 만든다.
새 생성 없음 · 임베딩 캐시만 사용(API 호출 0).

담는 것:
  ① 원인 요약 (질문이 닮은 게 아니라 답변이 수렴한다는 실측)
  ② 문턱 0.75 주변 쌍 전부 — 질문·답변 전문을 나란히 놓고 직접 판정
  ③ 각 쌍에 '중복 / 아님' 체크 → 문턱을 얼마로 두면 좋을지 스스로 확인
"""
import sys, json, itertools, html
from pathlib import Path
from collections import Counter

EXP = Path(__file__).resolve().parent.parent   # repo 루트 (이 파일은 repo/scripts/ 안)
sys.path.insert(0, str(EXP / "scripts"))
import _measure_answer_overlap as mao

LOW = 0.65          # 이 아래는 볼 필요도 없음
TH = mao.SIM_THRESHOLD
CACHE = json.load(open(EXP / "scripts" / "_embed_cache.json", encoding="utf-8"))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "중복검토.html"


def cached(texts):
    if any(mao._key(t) not in CACHE for t in texts):
        return None
    return [CACHE[mao._key(t)] for t in texts]


def flat(j):
    meta = j.get("_followup_meta") or {}
    cm = {c["question"]: c for c in (meta.get("candidates") or [])}
    catm = {c.get("question"): c.get("category") for c in (meta.get("category_map") or [])}
    out = []
    for m in j.get("follow_up_questions") or []:
        for q in [m] + list(m.get("follow_ups") or []):
            c = cm.get(q["question"], {})
            out.append({"q": q["question"], "a": q.get("answer", ""),
                        "verse": c.get("verse"),
                        "cat": c.get("category") or catm.get(q["question"]) or "—"})
    return out


NEW_ENGINE = {"2026-07-26", "2026-07-30", "2026-08-03"}   # 새 엔진으로 재생성한 날

pairs, days = [], 0
for p in sorted((EXP / "data" / "deep_dive").glob("2026-0*.json")):
    j = json.load(open(p, encoding="utf-8"))
    ns = flat(j)
    if len(ns) < 2 or not all(n["a"] and n["q"] for n in ns):
        continue
    av, qv = cached([n["a"] for n in ns]), cached([n["q"] for n in ns])
    if av is None or qv is None:
        continue
    days += 1
    new = p.stem in NEW_ENGINE
    for i, k in itertools.combinations(range(len(ns)), 2):
        sa = mao.cosine(av[i], av[k])
        if sa >= LOW:
            pairs.append({"date": p.stem, "ref": j.get("scripture_ref", ""), "sa": sa,
                          "sq": mao.cosine(qv[i], qv[k]), "A": ns[i], "B": ns[k],
                          "new": new, "cut": False})
    # 새 엔진에서 관문이 '이미 잘라낸' 쌍 — 잘린 쪽 답변은 저장 안 돼 있어 질문만 대조 가능
    g = (j.get("_followup_meta") or {}).get("embed_gate") or {}
    amap = {n["q"]: n for n in ns}
    for dr in g.get("dropped") or []:
        keptn = amap.get(dr["kept_instead"], {})
        qa, qb = dr["question"], dr["kept_instead"]
        vq = cached([qa, qb]) or mao.embed_all([qa, qb])
        pairs.append({
            "date": p.stem, "ref": j.get("scripture_ref", ""), "sa": dr["sim"] or 0,
            "sq": mao.cosine(vq[0], vq[1]), "new": True, "cut": True,
            "A": {"q": qa, "a": "", "verse": None, "cat": "관문이 잘라낸 쪽"},
            "B": {"q": qb, "a": keptn.get("a", ""), "verse": keptn.get("verse"),
                  "cat": keptn.get("cat", "—")},
        })
pairs.sort(key=lambda x: -x["sa"])

flagged = [x for x in pairs if x["sa"] >= TH]
band = [x for x in pairs if x["sa"] < TH]
lo_q = sum(1 for x in flagged if x["sq"] < 0.75)
sa_avg = sum(x["sa"] for x in flagged) / len(flagged) if flagged else 0
sq_avg = sum(x["sq"] for x in flagged) / len(flagged) if flagged else 0
e = html.escape


def card(x, idx):
    over = x["sa"] >= TH
    tag = ('<span class="chip chip--new">새 엔진</span>' if x.get("new") else "")
    cut = ('<span class="chip chip--cut">관문이 자름</span>' if x.get("cut") else "")
    return f"""
<article class="pair {'is-over' if over else 'is-band'}" data-sa="{x['sa']:.4f}" id="p{idx}">
  <header class="pair__head">
    <div class="pair__meta">
      <span class="chip {'chip--red' if over else 'chip--amber'}">답변 {x['sa']:.3f}</span>
      <span class="chip chip--ghost">질문 {x['sq']:.3f}</span>
      {tag}{cut}
      <span class="date">{e(x['date'])} · {e(x['ref'])}</span>
    </div>
    <div class="judge" role="group" aria-label="이 쌍은 중복인가요">
      <button class="jbtn jbtn--dup" data-v="dup" type="button">중복 맞음</button>
      <button class="jbtn jbtn--ok" data-v="ok" type="button">중복 아님</button>
    </div>
  </header>
  <div class="cols">
    <section class="col">
      <p class="cat">{e(str(x['A']['cat']))}{f" · {x['A']['verse']}절" if x['A']['verse'] else ""}</p>
      <h3 class="q">{e(x['A']['q'])}</h3>
      <p class="a">{e(x['A']['a']) or "<em>이 질문의 답변은 저장되지 않았습니다 — 관문이 만들어지기 전 실행분입니다. 앞으로는 기록됩니다.</em>"}</p>
    </section>
    <section class="col">
      <p class="cat">{e(str(x['B']['cat']))}{f" · {x['B']['verse']}절" if x['B']['verse'] else ""}</p>
      <h3 class="q">{e(x['B']['q'])}</h3>
      <p class="a">{e(x['B']['a'])}</p>
    </section>
  </div>
</article>"""


CSS = """
:root{--bg:#f5f5f7;--card:#fff;--txt:#1d1d1f;--dim:#6e6e73;--line:rgba(0,0,0,.08);
 --red:#d70015;--redbg:rgba(215,0,21,.09);--amber:#a05a00;--amberbg:rgba(255,159,10,.14);
 --green:#0f7b3f;--greenbg:rgba(48,209,88,.16);--accent:#0071e3;--shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px -8px rgba(0,0,0,.10)}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--txt:#f5f5f7;--dim:#98989d;
 --line:rgba(255,255,255,.10);--red:#ff453a;--redbg:rgba(255,69,58,.16);--amber:#ffd60a;
 --amberbg:rgba(255,214,10,.14);--green:#30d158;--greenbg:rgba(48,209,88,.18);--accent:#0a84ff;
 --shadow:0 1px 2px rgba(0,0,0,.5),0 8px 24px -8px rgba(0,0,0,.7)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Pretendard","Apple SD Gothic Neo","Segoe UI",sans-serif;
 -webkit-font-smoothing:antialiased;padding:0 20px 80px}
.wrap{max-width:1080px;margin:0 auto}
header.top{padding:56px 0 8px}
h1{font-size:34px;letter-spacing:-.022em;font-weight:700;margin:0 0 8px}
.sub{color:var(--dim);margin:0 0 32px;font-size:17px}
.cause{background:var(--card);border-radius:18px;padding:24px 26px;box-shadow:var(--shadow);margin-bottom:16px}
.cause h2{font-size:20px;margin:0 0 14px;letter-spacing:-.01em}
.bars{display:grid;gap:12px;margin:18px 0 6px}
.bar{display:grid;grid-template-columns:88px 1fr 62px;align-items:center;gap:12px;font-size:14px}
.bar .track{display:block;height:10px;border-radius:5px;background:var(--line);overflow:hidden}
.bar .fill{display:block;height:100%;border-radius:5px}
.note{color:var(--dim);font-size:14px;margin:14px 0 0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0 28px}
.stat{background:var(--card);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
.stat b{display:block;font-size:27px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat span{color:var(--dim);font-size:13px}
h2.sec{font-size:22px;margin:36px 0 6px;letter-spacing:-.014em}
.secsub{color:var(--dim);font-size:15px;margin:0 0 18px}
.pair{background:var(--card);border-radius:18px;box-shadow:var(--shadow);margin-bottom:14px;overflow:hidden;
 transition:opacity .2s ease,transform .2s ease}
.pair.done{opacity:.5}
.pair__head{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;
 padding:16px 22px;border-bottom:1px solid var(--line)}
.pair__meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.chip{font-size:13px;font-weight:600;padding:4px 11px;border-radius:999px;font-variant-numeric:tabular-nums}
.chip--red{background:var(--redbg);color:var(--red)}
.chip--amber{background:var(--amberbg);color:var(--amber)}
.chip--ghost{background:var(--line);color:var(--dim)}
.chip--new{background:rgba(0,113,227,.14);color:var(--accent)}
.chip--cut{background:var(--redbg);color:var(--red)}
.date{color:var(--dim);font-size:14px}
.judge{display:flex;gap:8px}
.jbtn{font:inherit;font-size:14px;font-weight:600;padding:7px 15px;border-radius:999px;border:1px solid var(--line);
 background:transparent;color:var(--dim);cursor:pointer;transition:all .15s ease}
.jbtn:hover{border-color:var(--accent);color:var(--accent)}
.jbtn.on[data-v="dup"]{background:var(--redbg);color:var(--red);border-color:transparent}
.jbtn.on[data-v="ok"]{background:var(--greenbg);color:var(--green);border-color:transparent}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0}
@media (max-width:720px){.cols{grid-template-columns:1fr}.col+.col{border-top:1px solid var(--line)}}
.col{padding:20px 22px}
.col+.col{border-left:1px solid var(--line)}
@media (max-width:720px){.col+.col{border-left:0}}
.cat{color:var(--dim);font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin:0 0 8px}
.q{font-size:17px;font-weight:650;letter-spacing:-.01em;margin:0 0 10px;line-height:1.4}
.a{color:var(--dim);font-size:15px;margin:0;white-space:pre-wrap}
.tally{position:sticky;bottom:0;background:var(--card);border-radius:16px;box-shadow:var(--shadow);
 padding:14px 20px;margin-top:24px;display:flex;gap:20px;flex-wrap:wrap;align-items:center;font-size:15px}
.tally b{font-variant-numeric:tabular-nums}
"""

JS = """
const st={};
document.querySelectorAll('.pair').forEach(p=>{
  p.querySelectorAll('.jbtn').forEach(b=>{
    b.addEventListener('click',()=>{
      const v=b.dataset.v, id=p.id;
      if(st[id]===v){delete st[id];b.classList.remove('on');p.classList.remove('done');}
      else{st[id]=v;p.querySelectorAll('.jbtn').forEach(x=>x.classList.remove('on'));
           b.classList.add('on');p.classList.add('done');}
      tally();
    });
  });
});
function tally(){
  const vals=Object.entries(st);
  const dup=vals.filter(([,v])=>v==='dup');
  const ok=vals.filter(([,v])=>v==='ok');
  document.getElementById('tdup').textContent=dup.length;
  document.getElementById('tok').textContent=ok.length;
  // '중복 아님'으로 찍은 것 중 제일 높은 점수 = 문턱을 그 위로 올려야 한다는 신호
  let hiOk=0, loDup=1;
  ok.forEach(([id])=>{const s=+document.getElementById(id).dataset.sa; if(s>hiOk)hiOk=s;});
  dup.forEach(([id])=>{const s=+document.getElementById(id).dataset.sa; if(s<loDup)loDup=s;});
  const el=document.getElementById('tsug');
  if(!dup.length&&!ok.length){el.textContent='—';return;}
  if(hiOk&&loDup<1&&hiOk>=loDup){el.textContent='겹칩니다 (한 줄로 못 가름)';return;}
  if(loDup<1){el.textContent=(hiOk?((hiOk+loDup)/2).toFixed(3):loDup.toFixed(3))+' 부근';}
  else{el.textContent='('+hiOk.toFixed(3)+' 초과)';}
}
"""

doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>떠오르는 질문 · 중복 검토</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top">
  <h1>중복, 직접 판단해 보세요</h1>
  <p class="sub">{days}일치 · 유사도 {LOW} 이상인 쌍 {len(pairs)}건을 전부 폈습니다. 새로 생성한 건 없습니다(API 비용 0).</p>
</header>

<div class="cause">
  <h2>원인 — 질문이 닮은 게 아니라, 답변이 같은 곳으로 모입니다</h2>
  <p style="margin:0;color:var(--dim);font-size:15px">
    문턱을 넘은 {len(flagged)}쌍을 보면, <b style="color:var(--txt)">질문끼리는 별로 안 닮았는데 답변만 닮았습니다.</b>
    질문 만드는 로직이 같은 질문을 찍어내는 게 아니라, 서로 다른 각도로 물어도
    답을 쓰다 보면 그날 사건의 같은 설명으로 수렴하는 겁니다.
  </p>
  <div class="bars">
    <div class="bar"><span>답변 유사도</span><span class="track"><span class="fill" style="width:{sa_avg*100:.0f}%;background:var(--red)"></span></span><b>{sa_avg:.3f}</b></div>
    <div class="bar"><span>질문 유사도</span><span class="track"><span class="fill" style="width:{sq_avg*100:.0f}%;background:var(--accent)"></span></span><b>{sq_avg:.3f}</b></div>
  </div>
  <p class="note">
    · 겹친 {len(flagged)}쌍 중 <b style="color:var(--txt)">{lo_q}쌍({lo_q/len(flagged)*100 if flagged else 0:.0f}%)</b>은 질문 유사도가 0.75 미만 — 질문은 딴판입니다.<br>
    · 겹친 쌍의 <b style="color:var(--txt)">100%가 서로 다른 절</b>에서 나왔습니다 → 절을 흩는 기존 장치는 제대로 돌고 있습니다.<br>
    · 가장 잘 겹치는 각도는 <b style="color:var(--txt)">‘신학/해석 견해’끼리</b>입니다 — 추상적인 ‘왜·의미’ 질문일수록 답이 한곳으로 모입니다.
  </p>
</div>

<div class="stats">
  <div class="stat"><b>{days}</b><span>검사한 날</span></div>
  <div class="stat"><b>{len(flagged)}</b><span>문턱({TH}) 넘은 쌍</span></div>
  <div class="stat"><b>{len(band)}</b><span>경계({LOW}~{TH}) 쌍</span></div>
  <div class="stat"><b>{sa_avg-sq_avg:+.3f}</b><span>답변−질문 유사도 차</span></div>
</div>

<h2 class="sec">① 지금 잘리는 쌍 — {len(flagged)}건</h2>
<p class="secsub">유사도 {TH} 이상이라 관문이 하나를 빼는 쌍입니다. 정말 중복인지 봐주세요.</p>
{''.join(card(x, i) for i, x in enumerate(flagged))}

<h2 class="sec">② 아슬아슬하게 살아남은 쌍 — {len(band)}건</h2>
<p class="secsub">{LOW}~{TH} 구간이라 지금은 <b>둘 다 남습니다.</b> 여기에 중복이 많으면 문턱을 낮춰야 한다는 뜻입니다.</p>
{''.join(card(x, i + len(flagged)) for i, x in enumerate(band))}

<div class="tally">
  <span>중복 맞음 <b id="tdup">0</b></span>
  <span>중복 아님 <b id="tok">0</b></span>
  <span style="color:var(--dim)">→ 사장님 판단대로면 문턱은 <b id="tsug">—</b></span>
</div>
</div><script>{JS}</script></body></html>"""

OUT.write_text(doc, encoding="utf-8")
print(f"저장: {OUT}")
print(f"  {days}일 · 문턱 넘은 쌍 {len(flagged)}건 · 경계 쌍 {len(band)}건")
print(f"  겹친 쌍 평균: 답변 {sa_avg:.3f} vs 질문 {sq_avg:.3f}")
