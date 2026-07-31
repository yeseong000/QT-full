# _regen_followup_date.py — 로컬 전용(커밋 안 함)
# 특정 날짜의 '떠오르는 질문'만 새 코드(followup_simple.run_simple)로 재생성한다.
# 5단 묵상·장면·이미지는 그대로 두고, follow_up_questions / _cost_followup / _followup_meta 세 필드만 교체.
# 사용: python scripts/_regen_followup_date.py 2026-07-27 2026-07-28   (앞 날짜부터 순서대로 = history 반영)
import sys, json, shutil
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_meditation as gm
import followup_simple as fs

try:
    from dotenv import load_dotenv
    load_dotenv(gm.PROJECT_ROOT / ".env")
except ImportError:
    pass


def regen(date: str):
    path = gm.DEEP_DIVE_DIR / f"{date}.json"
    existing = json.loads(path.read_text(encoding="utf-8"))

    qt = gm.load_qt_data(date)
    kb_full = gm.load_kb(qt.get("book_name", ""))
    kb = gm.slice_kb_to_passage(kb_full, qt)
    history = gm.load_same_book_followup_history(qt)
    # 저장 파일의 최상위 5키(장면/질문/맥락/통찰/연결)는 항상 variants[0]와 동일 → 그대로 deep5로 사용
    deep5 = existing

    items, cost, meta = fs.run_simple(
        gm._fu_chat_v2, qt, kb, deep5, history=history, log=gm.log
    )

    shutil.copy(str(path), str(path) + ".prefix.bak")
    existing["follow_up_questions"] = items
    existing["_cost_followup"] = cost
    existing["_followup_meta"] = meta
    gm.save_json(existing, path)
    print(
        f"[DONE] {date} method={meta.get('generation_method')} "
        f"candidate_count={meta.get('candidate_count')} "
        f"distinct={meta.get('distinct_knowledge_in_final')}/9 "
        f"gpt_calls={meta.get('gpt_calls')} fix_rounds={meta.get('fix_rounds')}"
    )


if __name__ == "__main__":
    dates = sys.argv[1:]
    if not dates:
        print("날짜를 지정하세요. 예: python scripts/_regen_followup_date.py 2026-07-27 2026-07-28")
        sys.exit(1)
    for d in dates:
        regen(d)
