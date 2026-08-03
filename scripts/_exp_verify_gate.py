# -*- coding: utf-8 -*-
"""실제 생성분에 임베딩 관문을 적용해 본다 — 캐시된 임베딩만 쓰므로 비용 0.
지난 세션이 만들어 둔 data/deep_dive/*.json(새 엔진 결과)을 그대로 통과시켜
'몇 개가 남는가 · 무엇이 왜 빠지는가'를 확인한다."""
import sys, json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent   # repo 루트 (이 파일은 repo/scripts/ 안)
sys.path.insert(0, str(EXP / "scripts"))
import followup_simple as fs
import _measure_answer_overlap as mao   # embed_all = 캐시 사용(재실행 무료)

CACHE = json.load(open(EXP / "scripts" / "_embed_cache.json", encoding="utf-8"))
print(f"캐시된 임베딩 {len(CACHE)}개 · 문턱 {fs._SIM_THRESHOLD}\n")


ALLOW_API = "--api" in sys.argv
if ALLOW_API:
    sys.argv.remove("--api")


def embed(texts):
    """캐시 우선. --api를 안 주면 캐시에 없는 날은 건너뛴다(=API 호출 0 보장)."""
    missing = [t for t in texts if mao._key(t) not in CACHE]
    if missing and not ALLOW_API:
        raise RuntimeError(f"캐시에 없는 답변 {len(missing)}개 — 이 날은 건너뜀")
    if missing:
        print(f"    (캐시에 없는 {len(missing)}개만 임베딩 호출)")
        return mao.embed_all(texts)      # 내부에서 캐시에 저장 → 다음부터 무료
    return [CACHE[mao._key(t)] for t in texts]


def log(msg, lv="INFO"):
    print(f"    {msg}")


dates = sys.argv[1:] or sorted(p.stem for p in (EXP / "data" / "deep_dive").glob("2026-0*.json"))
rows = []
for d in dates:
    j = json.load(open(EXP / "data" / "deep_dive" / f"{d}.json", encoding="utf-8"))
    items = j.get("follow_up_questions") or []
    meta = j.get("_followup_meta") or {}
    if not items:
        continue
    before = sum(1 + len(m.get("follow_ups") or []) for m in items)
    try:
        out, m2 = fs.apply_embed_gate(items, meta, embed, log=None)
    except RuntimeError as e:
        print(f"=== {d} · {j.get('scripture_ref','')} — 건너뜀 ({e})")
        continue
    g = m2.get("embed_gate")
    if not g:
        print(f"=== {d} — 관문 미적용(답변 누락?)")
        continue
    after = g["final_count"]
    mark = "  ← 잘림" if g["dropped_by_embed"] else ""
    print(f"=== {d} · {j.get('scripture_ref','')} : {before}개 → {after}개 "
          f"(겹침쌍 {g['flagged_pairs']} · 최고 {g['max_sim']} · 메인 {g['mains_after']}가지 "
          f"· 관주 {g['gwanju_kept']}){mark}")
    for dr in g["dropped"]:
        print(f"      뺌(뜻 {dr['sim']}): {dr['question'][:52]}")
        print(f"          남긴 것    : {dr['kept_instead'][:52]}")
    for p in g["promoted"]:
        print(f"      꼬리 승격: {p['from'][:52]}")
    # 관문 통과 후 정말 겹침이 0인지 재검사(자기검증)
    _out2, m3 = fs.apply_embed_gate(out, m2, embed, log=None)
    resid = m3["embed_gate"]["dropped_by_embed"] if m3.get("embed_gate") else "?"
    assert resid == 0, f"{d}: 관문 통과 후에도 겹침 {resid}건 남음!"
    rows.append((d, before, after, g["mains_after"], g["gwanju_kept"]))

print("\n" + "=" * 62)
print(f"{'날짜':<12}{'전':>4}{'후':>4}{'메인가지':>8}{'관주':>5}")
for d, b, a, mn, gw in rows:
    print(f"{d:<12}{b:>4}{a:>4}{mn:>8}{gw:>5}")
if rows:
    kept9 = sum(1 for _d, b, a, _m, _g in rows if a == b)
    print(f"\n{len(rows)}일 중 {kept9}일이 그대로 유지 · {len(rows)-kept9}일이 축소")
    print("관문 통과 후 잔여 겹침 0건 — 자기검증 통과 ✅")
