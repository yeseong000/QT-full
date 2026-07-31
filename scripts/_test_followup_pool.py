"""followup_pool.py(v3) 수동 테스트 하네스 — 운영 코드 아님.

지정한 날짜에 대해 fup.run_pipeline()만 독립 실행하고 결과를 출력한다.
generate_meditation.py의 로더(load_qt_data/load_kb/slice_kb_to_passage/
load_same_book_followup_history)를 그대로 재사용해 실제 파이프라인과
같은 입력을 만든다.

사용법:
    python scripts/_test_followup_pool.py 2026-07-09              # 결과만 출력
    python scripts/_test_followup_pool.py 2026-07-09 --write       # data/deep_dive/{date}.json에 반영(백업 후 덮어씀)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import generate_meditation as gm
import followup_pool as fup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(gm.PROJECT_ROOT / ".env")
        load_dotenv("C:/Users/USER/Desktop/앱 개발/7.주만나 큐티/.env")
    except ImportError:
        pass

    qt_data = gm.load_qt_data(args.date)
    kb_full = gm.load_kb(qt_data.get("book_name", ""))
    kb = gm.slice_kb_to_passage(kb_full, qt_data)

    deep_path = gm.DEEP_DIVE_DIR / f"{args.date}.json"
    deep = json.loads(deep_path.read_text(encoding="utf-8")) if deep_path.exists() else {}
    deep5 = {k: deep.get(k, "") for k in gm.REQUIRED_KEYS}

    history = gm.load_same_book_followup_history(qt_data)

    print(f"=== {args.date} / {qt_data.get('scripture_ref')} ===")
    print(f"KB: {'있음' if kb else '없음'} / 히스토리 {len(history)}개")

    items, cost, meta = fup.run_pipeline(gm._fu_chat_v2, qt_data, kb, deep5, history=history, log=gm.log)

    print("\n--- 결과 ---")
    print(f"카테고리 제외: {meta['dropped_categories']}")
    print(f"KB 커버리지: {meta['kb_coverage']}")
    print(f"후보 시도: {meta['candidate_attempts']}회 / 후보 풀: {meta['candidate_pool_count']}개")
    print(f"그라운딩 라운드: {meta['grounding_rounds']}회")
    print(f"비용: 토큰 {cost['total_tokens']} / 약 {cost['cost_krw']:.2f}원")
    print("\n--- 9개 질문 ---")
    n = 0
    for i, m in enumerate(items, 1):
        n += 1
        print(f"{i}. [메인] {m['question']}  ({(m['answer'].count(chr(10)*2)+1)}단락/{len(m['answer'])}자)")
        for j, t in enumerate(m["follow_ups"], 1):
            n += 1
            print(f"   {i}-{j}. [꼬리] {t['question']}  ({(t['answer'].count(chr(10)*2)+1)}단락/{len(t['answer'])}자)")
    print(f"\n총 {n}개")

    if args.write:
        if deep_path.exists():
            bak_path = deep_path.with_suffix(".json.bak")
            bak_path.write_text(deep_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"\n백업: {bak_path}")
        deep["follow_up_questions"] = items
        deep["_cost_followup"] = cost
        deep["_followup_meta"] = meta
        deep_path.write_text(json.dumps(deep, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"저장 완료: {deep_path}")


if __name__ == "__main__":
    main()
