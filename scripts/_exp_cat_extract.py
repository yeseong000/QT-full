# -*- coding: utf-8 -*-
"""카테고리 한 종류만 날짜별로 전부 뽑아, 그날 KB에 실제로 있던 재료와 나란히 놓는다.
"이 질문이 재료에 근거했나, 아니면 지어냈나"를 눈으로 보려는 도구.

사용: python scripts/_exp_cat_extract.py "신학/해석 견해" [--html 파일명]
새 생성 없음 · 임베딩은 캐시만(API 0).
"""
import sys, json, itertools, html
from pathlib import Path
from collections import defaultdict

EXP = Path(__file__).resolve().parent.parent   # repo 루트
sys.path.insert(0, str(EXP / "scripts"))
import followup_simple as fs
import _measure_answer_overlap as mao

CACHE_P = EXP / "scripts" / "_embed_cache.json"
CACHE = json.load(open(CACHE_P, encoding="utf-8")) if CACHE_P.exists() else {}

# 질문 카테고리 → KB key_details.cat (이 카테고리가 원래 먹고 살아야 할 재료)
CAT2KB = {"주석형/본문관찰": ["본문관찰"], "본문 디테일": ["본문관찰"],
          "신학/해석 견해": ["신학핵심"], "문화·관습": ["문화관습"],
          "지명 정보": ["지리"], "어원·유래": ["어원"], "인물 배경": ["인물배경"],
          "연결 질문": [], "랜덤": []}


def cached(ts):
    if any(mao._key(t) not in CACHE for t in ts):
        return None
    return [CACHE[mao._key(t)] for t in ts]


def kb_material(book, chap_lo, chap_hi, kbcats):
    """그 날 본문이 걸친 장들의 해당 cat key_details + 관련 필드."""
    p = EXP / "data" / "reference" / f"{book}.json"
    if not p.exists():
        return [], []
    kb = json.load(open(p, encoding="utf-8"))
    facts, extra = [], []
    for c in range(chap_lo, chap_hi + 1):
        ch = kb.get(str(c))
        if not isinstance(ch, dict):
            continue
        for d in ch.get("key_details") or []:
            if d.get("cat") in kbcats:
                facts.append(f"{d.get('verse')} · {d.get('fact')}")
        if "신학핵심" in kbcats:
            if ch.get("신학_핵심"):
                extra.append(f"[{c}장 신학_핵심] {ch['신학_핵심'][:300]}")
            for w in (ch.get("주의점") or [])[:6]:
                extra.append(f"[{c}장 주의점] {w}")
        if "인물배경" in kbcats:
            for pr in (ch.get("인물") or []):
                extra.append(f"[{c}장 인물] {pr.get('인물')}: {pr.get('배경','')}")
    return facts, extra


def chap_range(ref):
    """'사무엘하 13:30-39' → ('사무엘하', 13, 13). 장이 걸치면 범위로."""
    try:
        book, rest = ref.rsplit(" ", 1)
        parts = rest.split("-")
        lo = int(parts[0].split(":")[0])
        hi = int(parts[-1].split(":")[0]) if ":" in parts[-1] else lo
        return book, lo, max(lo, hi)
    except Exception:
        return "", 0, -1


def collect(target):
    kbcats = CAT2KB.get(target, [])
    days = []
    for p in sorted((EXP / "data" / "deep_dive").glob("2026-0*.json")):
        j = json.load(open(p, encoding="utf-8"))
        meta = j.get("_followup_meta") or {}
        cm = {c["question"]: c for c in (meta.get("candidates") or [])}
        catm = {c.get("question"): c.get("category") for c in (meta.get("category_map") or [])}
        nodes = []
        for it in j.get("follow_up_questions") or []:
            for q in [it] + list(it.get("follow_ups") or []):
                c = cm.get(q["question"], {})
                cat = fs._canon_cat(c.get("category") or catm.get(q["question"]) or "")
                nodes.append({"q": q["question"], "a": q.get("answer", ""), "cat": cat,
                              "verse": c.get("verse"), "anchor": c.get("anchor"),
                              "atype": c.get("anchor_type"), "ok": c.get("anchor_ok")})
        if not nodes or not all(n["a"] for n in nodes):
            continue
        # 그날 어떤 질문이 겹쳤는지
        v = cached([n["a"] for n in nodes])
        bad = set()
        if v:
            for i, k in itertools.combinations(range(len(nodes)), 2):
                if mao.cosine(v[i], v[k]) >= 0.75:
                    bad.add(i); bad.add(k)
        hits = [(i, n) for i, n in enumerate(nodes) if n["cat"] == target]
        if not hits:
            continue
        ref = j.get("scripture_ref", "")
        book, lo, hi = chap_range(ref)
        facts, extra = kb_material(book, lo, hi, kbcats) if kbcats else ([], [])
        days.append({"date": p.stem, "ref": ref, "facts": facts, "extra": extra,
                     "hits": [{**n, "dup": i in bad} for i, n in hits],
                     "total": len(nodes)})
    return days


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = args[0] if args else "신학/해석 견해"
    days = collect(target)
    nq = sum(len(d["hits"]) for d in days)
    ndup = sum(1 for d in days for h in d["hits"] if h["dup"])
    grounded = sum(1 for d in days for h in d["hits"] if h["atype"] == "KB")
    print(f"=== '{target}' — {len(days)}일 · 질문 {nq}개 · 겹침 연루 {ndup}개"
          f" · KB 근거 표기 {grounded}개 ===\n")
    for d in days:
        print(f"── {d['date']} · {d['ref']}  (절 재료 {len(d['facts'])}개 + 장 재료 {len(d['extra'])}개"
              f" / 이 카테고리 질문 {len(d['hits'])}개)")
        for h in d["hits"]:
            mark = "⚠겹침" if h["dup"] else "  ok  "
            print(f"   {mark} [{h['atype']}/{h['verse']}] {h['q']}")
        if d["facts"]:
            for f in d["facts"][:4]:
                print(f"        재료: {f[:96]}")
        else:
            print(f"        재료: (이 카테고리용 KB 재료 0개)")
        print()
    # 요약: 재료 대비 질문 수
    tot_f = sum(len(d["facts"]) + len(d["extra"]) for d in days)
    print(f"[요약] 재료 {tot_f}개 · 질문 {nq}개 → {nq/tot_f if tot_f else 0:.1f}배 사용"
          f" · 겹침 연루 {ndup}/{nq} ({ndup/nq*100 if nq else 0:.0f}%)")
    no_mat = [d["date"] for d in days if not d["facts"] and not d["extra"]]
    if no_mat:
        print(f"[경고] 재료가 0개인데 질문을 만든 날: {len(no_mat)}일 — {', '.join(no_mat[:8])}")

    if "--html" in sys.argv:
        out = EXP.parent / f"카테고리연구_{target.replace('/','_')}.html"
        e = html.escape
        rows = []
        for d in days:
            qs = "".join(
                f"<div class='q {'dup' if h['dup'] else ''}'><b>{e(h['q'])}</b>"
                f"<span class='meta'>{e(str(h['atype']))} · {h['verse']}절"
                f"{' · 겹침' if h['dup'] else ''}</span>"
                f"<p>{e(h['a'])}</p></div>" for h in d["hits"])
            fac = "".join(f"<li>{e(f)}</li>" for f in d["facts"]) or "<li class='none'>이 카테고리용 KB 재료 0개</li>"
            ext = "".join(f"<li>{e(x)}</li>" for x in d["extra"][:6])
            rows.append(f"<section><h2>{e(d['date'])} · {e(d['ref'])}</h2>"
                        f"<div class='cols'><div><h3>질문 {len(d['hits'])}개</h3>{qs}</div>"
                        f"<div><h3>그날 KB 재료 {len(d['facts'])}개</h3><ul>{fac}</ul>"
                        f"{'<h3>장 차원 자료</h3><ul>' + ext + '</ul>' if ext else ''}</div></div></section>")
        css = ("body{font:15px/1.65 -apple-system,'Apple SD Gothic Neo','Segoe UI',sans-serif;"
               "max-width:1180px;margin:0 auto;padding:32px 20px 80px;background:#f5f5f7;color:#1d1d1f}"
               "@media(prefers-color-scheme:dark){body{background:#000;color:#f5f5f7}"
               "section{background:#1c1c1e!important}.q{background:#2c2c2e!important}}"
               "h1{font-size:30px;letter-spacing:-.02em}"
               "section{background:#fff;border-radius:16px;padding:20px 24px;margin:16px 0;"
               "box-shadow:0 1px 2px rgba(0,0,0,.05),0 8px 24px -10px rgba(0,0,0,.12)}"
               "h2{font-size:18px;margin:0 0 14px}h3{font-size:13px;color:#6e6e73;"
               "text-transform:uppercase;letter-spacing:.05em;margin:0 0 10px}"
               ".cols{display:grid;grid-template-columns:1.15fr 1fr;gap:24px}"
               "@media(max-width:820px){.cols{grid-template-columns:1fr}}"
               ".q{background:#f5f5f7;border-radius:12px;padding:12px 14px;margin-bottom:10px}"
               ".q.dup{box-shadow:inset 3px 0 0 #d70015}"
               ".q .meta{display:block;font-size:12px;color:#6e6e73;margin:4px 0 8px}"
               ".q p{margin:0;font-size:14px;color:#48484a;white-space:pre-wrap}"
               "@media(prefers-color-scheme:dark){.q p{color:#aeaeb2}}"
               "ul{margin:0;padding-left:18px;font-size:13.5px;color:#48484a}"
               "@media(prefers-color-scheme:dark){ul{color:#aeaeb2}}"
               "li{margin-bottom:6px}.none{color:#d70015}")
        doc = (f"<!doctype html><meta charset='utf-8'><title>카테고리 연구 · {e(target)}</title>"
               f"<style>{css}</style><h1>‘{e(target)}’ 날짜별 전수</h1>"
               f"<p>{len(days)}일 · 질문 {nq}개 · 겹침 {ndup}개 · 재료 {tot_f}개"
               f" → <b>{nq/tot_f if tot_f else 0:.1f}배 사용</b></p>" + "".join(rows))
        out.write_text(doc, encoding="utf-8")
        print(f"\nHTML: {out}")


if __name__ == "__main__":
    main()
