# _bestofn_test.py — 로컬 전용(커밋 안 함)
# '베스트-of-N' 프로토타입: 각 날짜를 새 코드로 N번 생성 → 매번 정직한 잣대(임베딩 겹침) 측정 →
# 제일 안 겹치는 세트를 자동 선택(=베스트-of-N) → 옛 코드(현 운영 파일)와 비교.
# 운영 파일/백업 안 건드림(임시 파일만). 이게 통하면 그대로 실제 기능 명세가 된다.
# 사용: python scripts/_bestofn_test.py 3 2026-06-20 2026-07-21 2026-07-14 2026-07-24 2026-07-16
import sys, json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_meditation as gm
import followup_simple as fs
import _measure_answer_overlap as meas

try:
    from dotenv import load_dotenv
    load_dotenv(gm.PROJECT_ROOT / ".env")
except ImportError:
    pass

TMP = Path(__file__).resolve().parent / "_bestofn_tmp.json"


def quiet(*a, **k):
    pass


def score(rr):
    # 낮을수록 좋음: (겹침쌍 수, 최고유사도)
    return (len(rr["sim_flagged"]), round(rr["max_sim"], 4))


def main():
    argv = sys.argv[1:]
    N = 3
    dates = []
    for a in argv:
        if a.isdigit():
            N = int(a)
        elif a.startswith("2026"):
            dates.append(a)
    if not dates:
        print("사용: python scripts/_bestofn_test.py 3 2026-06-20 2026-07-21 ...")
        return 1

    print(f"=== 베스트-of-{N} 프로토타입 (옛 코드 vs 새 코드 N번 중 최선) ===\n", flush=True)
    summary = []
    for date in dates:
        qt = gm.load_qt_data(date)
        kb = gm.slice_kb_to_passage(gm.load_kb(qt.get("book_name", "")), qt)
        history = gm.load_same_book_followup_history(qt)
        old = meas.analyze(date)  # 현 운영 파일 = 옛 코드 (임베딩 캐시됨)
        old_f, old_m = len(old["sim_flagged"]), old["max_sim"]
        deep5 = json.loads((gm.DEEP_DIVE_DIR / (date + ".json")).read_text(encoding="utf-8"))

        print(f"===== {date} ({qt.get('scripture_ref')}) =====", flush=True)
        print(f"  옛 코드:  뜻겹침 {old_f}건 · 최고 {old_m:.2f}", flush=True)
        runs = []
        for r in range(1, N + 1):
            try:
                items, cost, m = fs.run_simple(gm._fu_chat_v2, qt, kb, deep5, history=history, log=quiet)
            except Exception as e:
                print(f"    run{r}: 실패(제외) — {str(e)[:70]}", flush=True)
                continue
            TMP.write_text(
                json.dumps({"follow_up_questions": items, "_followup_meta": m}, ensure_ascii=False),
                encoding="utf-8",
            )
            rr = meas.analyze(str(TMP))
            runs.append((score(rr), len(rr["sim_flagged"]), rr["max_sim"]))
            print(f"    run{r}: 뜻겹침 {len(rr['sim_flagged'])}건 · 최고 {rr['max_sim']:.2f}", flush=True)
        if not runs:
            print(f"  베스트-of-{N}: (N번 모두 실패 → 판정 불가)\n", flush=True)
            summary.append((date, old_f, old_m, None, None, "⚠️ 전부실패"))
            continue
        best = min(runs, key=lambda x: x[0])
        best_f, best_m = best[1], best[2]
        if best_f < old_f or (best_f == old_f and best_m < old_m - 0.01):
            verdict = "✅ 새(베스트) 이김"
        elif best_f == old_f:
            verdict = "= 동률"
        else:
            verdict = "❌ 새(베스트) 짐"
        print(f"  베스트-of-{N}: 뜻겹침 {best_f}건 · 최고 {best_m:.2f}  →  {verdict}\n", flush=True)
        summary.append((date, old_f, old_m, best_f, best_m, verdict))

    print("=== 요약 (옛 코드  vs  베스트-of-{}) ===".format(N), flush=True)
    for d, of_, om, bf, bm, v in summary:
        best_s = f"베스트 {bf}건({bm:.2f})" if bf is not None else "베스트 (실패)"
        print(f"  {d}:  옛 {of_}건({om:.2f})  →  {best_s}   {v}", flush=True)
    wins = sum(1 for *_x, v in summary if v.startswith("✅"))
    ties = sum(1 for *_x, v in summary if v.startswith("="))
    print(f"\n  종합: {len(summary)}일 중 이김 {wins} · 동률 {ties} · 짐 {len(summary)-wins-ties}", flush=True)
    if TMP.exists():
        TMP.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
