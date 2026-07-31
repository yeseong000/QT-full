"""STEP2 반복 측정 하네스 — 같은 날짜를 N회 돌려 평균·편차를 낸다. ※ 로컬 도구(_접두사).

왜 필요한가(2026-07-20):
  같은 코드로 4일치를 두 번 돌렸더니 겹침 합계가 3건 → 5건이었다. 7/15만 봐도 1건 → 4건.
  **회차 편차가 개편 효과보다 크다.** 그래서 한 번 돌린 결과로 "좋아졌다/나빠졌다"를 말하면
  틀린다(실제로 이 프로젝트에서 단발 결과를 보고 원인을 세 번 잘못 짚었다).
  체중이 하루 1kg씩 오르내리는 사람이 0.5kg 감량을 확인하려면 여러 번 재야 하는 것과 같다.

무엇을 재나 — 두 종류를 나눠 본다:
  ① 구조 지표(편차 없어야 정상) — 출처 기록 검증 실패, 복사본, GPT 교체 라운드, 서로 다른 절
  ② 결과 지표(편차 큼)         — 답변 뜻 겹침 건수(임베딩), 최고 유사도, 비용

주의: 기존(운영) 데이터는 날짜당 표본이 1개뿐이라 편차를 알 수 없다. 따라서 이 비교는
     '운영 1회 관측' vs '신규 N회 평균'이다. 운영값이 신규 분포 밖에 있으면 의미 있는
     차이일 가능성이 크지만, 엄밀한 통계 검정은 아니다.

사용:
  python scripts/_repeat_measure.py                       # 기본 4일 × 3회
  python scripts/_repeat_measure.py --runs 5              # 5회씩
  python scripts/_repeat_measure.py --dates 2026-07-16    # 특정 날짜만
  python scripts/_repeat_measure.py --report              # 이미 돌린 결과만 다시 집계
"""
import argparse
import json
import statistics as st
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

OUT_DIR = REPO / "scripts" / "_repeat"
RESULT = OUT_DIR / "results.json"
DEFAULT_DATES = ["2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"]


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env")
        load_dotenv(r"C:/Users/USER/Desktop/앱 개발/7.주만나 큐티/.env")
    except ImportError:
        pass


def run_once(date, idx):
    """한 회차 실행 → 결과 파일 경로. 운영 데이터는 건드리지 않는다."""
    import generate_meditation as gm
    import followup_simple as fs

    qt = gm.load_qt_data(date)
    kb = gm.slice_kb_to_passage(gm.load_kb(qt.get("book_name", "")), qt)
    deep_path = gm.DEEP_DIVE_DIR / f"{date}.json"
    deep = json.loads(deep_path.read_text(encoding="utf-8")) if deep_path.exists() else {}
    deep5 = {k: deep.get(k, "") for k in gm.REQUIRED_KEYS}
    history = gm.load_same_book_followup_history(qt)

    def quiet(msg, level="INFO"):
        if level in ("WARN", "ERR"):
            print(f"      {msg}")

    items, cost, meta = fs.run_simple(gm._fu_chat_v2, qt, kb, deep5,
                                      history=history, log=quiet)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"{date}_r{idx}.json"
    p.write_text(json.dumps({"items": items, "meta": meta, "cost": cost},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def measure(path):
    """한 회차 결과 → 지표 묶음."""
    import _measure_answer_overlap as mo
    r = mo.analyze(str(path))
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    m, cost = j["meta"], j["cost"]
    cands = m.get("candidates") or []
    uniq = len({c["question"] for c in cands})
    return {
        # ① 구조 지표
        "anchor_fail": m.get("anchor_verify_failed", 0),
        "copies": len(cands) - uniq,
        "fix_rounds": m.get("fix_rounds", 0),
        "distinct_verses": m.get("distinct_verses_in_final"),
        "candidates": m.get("candidate_count"),
        "xref_used": sum(1 for c in cands if c.get("selected") and c.get("anchor_type") == "관주"),
        "kb_used": sum(1 for c in cands if c.get("selected") and c.get("anchor_type") == "KB"),
        "safe_cat": sum(1 for c in cands if c.get("selected")
                        and c.get("category") in ("인물 배경", "문화·관습", "어원·유래", "지명 정보")),
        # ② 결과 지표
        "overlap": len(r["sim_flagged"]),
        "max_sim": round(r["max_sim"], 3),
        "cost": round(cost.get("cost_krw", 0), 1),
    }


def baseline(date):
    """운영(기존) 데이터 1회 관측."""
    import _measure_answer_overlap as mo
    r = mo.analyze(date)
    prod = json.loads((REPO / "data" / "deep_dive" / f"{date}.json").read_text(encoding="utf-8"))
    return {"overlap": len(r["sim_flagged"]), "max_sim": round(r["max_sim"], 3),
            "cost": round((prod.get("_cost_followup") or {}).get("cost_krw", 0), 1)}


def collect(dates, runs):
    _load_env()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(RESULT.read_text(encoding="utf-8")) if RESULT.exists() else {}
    total = len(dates) * runs
    n = 0
    for d in dates:
        data.setdefault(d, {"runs": []})
        for i in range(1, runs + 1):
            n += 1
            print(f"[{n}/{total}] {d} · {i}회차 …", flush=True)
            try:
                p = run_once(d, i)
                data[d]["runs"].append(measure(p))
            except Exception as e:
                print(f"      실패: {e}")
                traceback.print_exc(limit=1)
            RESULT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def _agg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "—"
    if len(vals) == 1:
        return f"{vals[0]}"
    return f"{st.mean(vals):.1f} ±{st.pstdev(vals):.1f} (최소{min(vals)}·최대{max(vals)})"


def report(data):
    print()
    print("=" * 78)
    print("① 구조 지표 — 코드가 세는 값. 편차가 없어야 정상이다.")
    print("=" * 78)
    print(f"{'날짜':12s} {'후보':>10s} {'복사본':>8s} {'출처검증실패':>12s} {'GPT교체':>8s} {'서로다른절':>12s}")
    for d, v in data.items():
        R = v["runs"]
        if not R:
            continue
        print(f"{d:12s} {_agg([r['candidates'] for r in R]):>10s} {_agg([r['copies'] for r in R]):>8s} "
              f"{_agg([r['anchor_fail'] for r in R]):>12s} {_agg([r['fix_rounds'] for r in R]):>8s} "
              f"{_agg([r['distinct_verses'] for r in R]):>12s}")

    print()
    print("=" * 78)
    print("② 결과 지표 — 독자가 실제로 겪는 중복. 편차가 크다.")
    print("=" * 78)
    print("목표는 '평균을 낮추는 것'이 아니라 **겹침 0건**이다 → 0건 달성률이 핵심 지표다.")
    print()
    print(f"{'날짜':12s} {'기존':>6s} {'회차별 겹침':>16s} {'0건 달성':>10s} {'평균':>14s}")
    b_tot, n_tot, zero_hit, zero_all = 0, [], 0, 0
    for d, v in data.items():
        R = v["runs"]
        if not R:
            continue
        b = baseline(d)
        ov = [r["overlap"] for r in R]
        b_tot += b["overlap"]
        n_tot.append(ov)
        z = sum(1 for x in ov if x == 0)
        zero_hit += z
        zero_all += len(ov)
        mark = "✅" if z == len(ov) else ("△" if z else "❌")
        print(f"{d:12s} {b['overlap']:>5d}건 {str(ov):>16s} {mark} {z}/{len(ov):<6d} {_agg(ov):>14s}")
    if zero_all:
        print()
        print(f"  ▶ **0건 달성률: {zero_hit}/{zero_all}회 ({zero_hit / zero_all * 100:.0f}%)**"
              f"  — 목표는 100%")

    if n_tot:
        runs_n = min(len(x) for x in n_tot)
        sums = [sum(x[i] for x in n_tot) for i in range(runs_n)]
        print()
        print(f"  4일 합계 — 기존 {b_tot}건  vs  신규 {_agg(sums)}   회차별 {sums}")
        mean = st.mean(sums)
        if runs_n >= 2:
            sd = st.pstdev(sums)
            print()
            if b_tot > mean + sd:
                print(f"  ▶ 판정: 기존({b_tot})이 신규 분포({mean:.1f} ±{sd:.1f}) 밖 — **개선으로 볼 만하다**")
            elif b_tot < mean - sd:
                print(f"  ▶ 판정: 기존({b_tot})이 신규보다 낮다 — **악화 가능성**")
            else:
                print(f"  ▶ 판정: 기존({b_tot})이 신규 분포({mean:.1f} ±{sd:.1f}) 안 — "
                      f"**차이를 확정할 수 없다(회차 더 필요)**")

    print()
    costs = [r["cost"] for v in data.values() for r in v["runs"]]
    xr = [r["xref_used"] for v in data.values() for r in v["runs"]]
    kb = [r.get("kb_used", 0) for v in data.values() for r in v["runs"]]
    safe = [r.get("safe_cat", 0) for v in data.values() for r in v["runs"]]
    if costs:
        print(f"  비용: 평균 {st.mean(costs):.0f}원/일")
        print(f"  출처 종류 채택(9개 중): 관주형 {st.mean(xr):.1f} · KB형 {st.mean(kb):.1f}")
        print(f"  배경지식 카테고리: 평균 {st.mean(safe):.1f}/9 ({st.mean(safe) / 9 * 100:.0f}%)  — 이전 41%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--dates", nargs="*", default=DEFAULT_DATES)
    ap.add_argument("--report", action="store_true", help="실행 없이 기존 결과만 집계")
    a = ap.parse_args()
    if a.report:
        if not RESULT.exists():
            raise SystemExit("아직 결과가 없습니다 — 먼저 실행하세요.")
        report(json.loads(RESULT.read_text(encoding="utf-8")))
        return 0
    report(collect(a.dates, a.runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
