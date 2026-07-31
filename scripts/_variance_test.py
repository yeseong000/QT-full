# _variance_test.py — 로컬 전용(커밋 안 함)
# 특정 날짜를 새 코드(followup_simple.run_simple)로 N회 재생성하고, 매 회 정직한 잣대(임베딩 겹침)를 측정.
# 운영 파일/백업은 절대 건드리지 않고 임시 파일에만 쓴다. deep5(원래 5단 묵상)는 .prefix.bak 원본에서 가져온다.
# 사용: python scripts/_variance_test.py 3 2026-07-27 2026-07-28
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

TMP = Path(__file__).resolve().parent / "_variance_tmp.json"


def quiet_log(*a, **k):
    pass


def main():
    argv = sys.argv[1:]
    runs = 3
    dates = []
    for a in argv:
        if a.isdigit():
            runs = int(a)
        elif a.startswith("2026"):
            dates.append(a)
    if not dates:
        print("사용: python scripts/_variance_test.py 3 2026-07-27 2026-07-28")
        return 1

    for date in dates:
        path = gm.DEEP_DIVE_DIR / f"{date}.json"
        bak = Path(str(path) + ".prefix.bak")
        base = json.loads((bak if bak.exists() else path).read_text(encoding="utf-8"))
        qt = gm.load_qt_data(date)
        kb = gm.slice_kb_to_passage(gm.load_kb(qt.get("book_name", "")), qt)
        history = gm.load_same_book_followup_history(qt)
        deep5 = base  # 최상위 5키 = 원래 묵상

        print(f"\n===== {date} ({qt.get('scripture_ref')}) · 새 코드 {runs}회 =====", flush=True)
        rows = []
        for r in range(1, runs + 1):
            items, cost, meta = fs.run_simple(
                gm._fu_chat_v2, qt, kb, deep5, history=history, log=quiet_log
            )
            TMP.write_text(
                json.dumps({"follow_up_questions": items, "_followup_meta": meta}, ensure_ascii=False),
                encoding="utf-8",
            )
            rr = meas.analyze(str(TMP))
            ns = len(rr["sim_flagged"])
            rows.append((ns, rr["max_sim"], meta.get("candidate_count")))
            worst = ""
            if rr["sim_flagged"]:
                p = rr["sim_flagged"][0]
                worst = f"  ← 최악쌍: '{rr['qs'][p['i']]['question'][:22]}…' ↔ '{rr['qs'][p['j']]['question'][:22]}…'"
            print(f"  run{r}: 뜻겹침 {ns}건 · 최고유사도 {rr['max_sim']:.2f} · 후보 {meta.get('candidate_count')}{worst}", flush=True)
        ns_list = [x[0] for x in rows]
        mx_list = [x[1] for x in rows]
        print(f"  >>> 뜻겹침 건수 {ns_list} (평균 {sum(ns_list)/len(ns_list):.1f}) · "
              f"최고유사도 {[f'{m:.2f}' for m in mx_list]} (평균 {sum(mx_list)/len(mx_list):.2f})", flush=True)

    if TMP.exists():
        TMP.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
