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

    # 운영과 똑같은 경로로 부른다 — run_best_of_n(판 고르기) + 임베딩 관문(가변 개수).
    # run_simple을 직접 부르면 관문을 건너뛰어 '운영에서 나올 결과'와 달라진다.
    items, cost, meta = fs.run_best_of_n(
        gm._fu_chat_v2, qt, kb, deep5, history=history, log=gm.log,
        n=gm.FOLLOW_UP_BEST_OF_N, embed=gm._embed_texts,
    )

    shutil.copy(str(path), str(path) + ".prefix.bak")
    existing["follow_up_questions"] = items
    existing["_cost_followup"] = cost
    existing["_followup_meta"] = meta
    gm.save_json(existing, path)
    g = meta.get("embed_gate") or {}
    total = sum(1 + len(m.get("follow_ups") or []) for m in items)
    print(
        f"[DONE] {date} method={meta.get('generation_method')} "
        f"candidate_count={meta.get('candidate_count')} "
        f"질문 {total}개(메인 {len(items)}가지) "
        f"관문:{g.get('dropped_by_embed', '-')}개뺌/최고유사도 {g.get('max_sim', '-')} "
        f"gpt_calls={meta.get('gpt_calls')} 비용 {cost.get('cost_krw', 0):.1f}원"
    )


if __name__ == "__main__":
    dates = sys.argv[1:]
    if not dates:
        print("날짜를 지정하세요. 예: python scripts/_regen_followup_date.py 2026-07-27 2026-07-28")
        sys.exit(1)
    for d in dates:
        regen(d)
