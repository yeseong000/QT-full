"""STEP2 A/B 시험 — 연결층 있음/없음으로 같은 날짜를 돌려 비교. 결과는 절대 안 쓴다(읽기전용).

운영 조건 그대로 재현:
  - history는 generate_meditation이 쓰는 것과 동일(그날 이전 날짜만)
  - kb는 slice_kb_to_passage로 그날 장만

사용:
  python ab_test_step2.py 2026-07-16 --arm after    # 연결층 있는 현재 KB로
  python ab_test_step2.py 2026-07-16 --arm before   # 연결층 걷어낸 KB로(대조군)
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\USER\Documents\Playground\qt-push-tmp")
sys.path.insert(0, str(REPO / "scripts"))

import generate_meditation as gm  # noqa: E402
import followup_simple as fs  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--arm", choices=["before", "after"], default="after")
    a = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env")
        load_dotenv(r"C:/Users/USER/Desktop/앱 개발/7.주만나 큐티/.env")
    except ImportError:
        pass

    qt = gm.load_qt_data(a.date)
    kb_full = gm.load_kb(qt.get("book_name", ""))
    kb = gm.slice_kb_to_passage(kb_full, qt)

    # before 팔: 연결층을 걷어내 예전 KB 상태를 그대로 만든다
    if a.arm == "before" and kb:
        kb = json.loads(json.dumps(kb))
        for k, v in kb.items():
            if k.isdigit() and isinstance(v, dict):
                v.pop("연결", None)

    n_links = sum(len(v.get("연결", [])) for k, v in (kb or {}).items()
                  if k.isdigit() and isinstance(v, dict))

    deep_path = gm.DEEP_DIVE_DIR / f"{a.date}.json"
    deep = json.loads(deep_path.read_text(encoding="utf-8")) if deep_path.exists() else {}
    deep5 = {k: deep.get(k, "") for k in gm.REQUIRED_KEYS}
    history = gm.load_same_book_followup_history(qt)

    print("=" * 62)
    print(f"[{a.arm.upper()}] {a.date} / {qt.get('scripture_ref')}")
    print(f"  연결층 {n_links}개 · 히스토리 {len(history)}개")
    print("=" * 62)

    items, cost, meta = fs.run_simple(gm._fu_chat_v2, qt, kb, deep5,
                                      history=history, log=gm.log)

    d = meta.get("distinct_knowledge_in_final")
    nv = meta.get("distinct_verses_in_final")
    pile = meta.get("verse_pileup") or {}
    print()
    print(f"### 서로 다른 지식: {d}/9 {'✅' if d >= 9 else '⚠️ 중복 ' + str(9 - d) + '개'}")
    # 자리 지표 — 코드가 본문과 대조해 센 값(모델 판단 아님)
    print(f"### 서로 다른 절: {nv}/9 (본문 {meta.get('passage_verse_count')}절)"
          + (f" · 겹친 절 {pile}" if pile else " · 절 겹침 없음"))
    print(f"### 출처 기록 검증 실패: {meta.get('anchor_verify_failed')}건")
    print(f"### 비용: {cost.get('cost_krw')}원 · 카테고리: {meta.get('covered_categories')}")
    print()
    sel = [c for c in (meta.get("candidates") or []) if c.get("selected")]
    for cl, n in Counter(c.get("cluster") for c in sel).items():
        if n > 1:
            print(f"  ⚠️ 같은 묶음({cl}) {n}개:")
            for c in sel:
                if c.get("cluster") == cl:
                    print(f"      · {c.get('question')}")
    print()
    anc = {c["question"]: c for c in (meta.get("candidates") or []) if c.get("selected")}

    def _tag(q):
        c = anc.get(q)
        if not c:
            return ""   # 교체(_qfix)된 질문은 후보 풀에 없다 — 출처 기록 없음
        return f"  [{c.get('verse')}절·{c.get('anchor', '')[:10]}]"

    for i, m in enumerate(items, 1):
        print(f"  MAIN{i}: {m['question']}{_tag(m['question'])}")
        for f in m.get("follow_ups", []):
            print(f"     └ {f['question']}{_tag(f['question'])}")

    out = Path(__file__).parent / f"ab_{a.date}_{a.arm}.json"
    out.write_text(json.dumps({"items": items, "meta": meta, "cost": cost},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n(결과 저장: {out.name} — 운영 데이터는 안 건드림)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
