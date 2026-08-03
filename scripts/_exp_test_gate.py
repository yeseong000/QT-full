# -*- coding: utf-8 -*-
"""임베딩 관문 단위 시험 — 가짜 벡터로 로직만 검증(API 비용 0).
답변 앞글자가 같으면 코사인 1.0(=겹침), 다르면 0.0이 되도록 원-핫 벡터를 만든다."""
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent   # repo 루트 (이 파일은 repo/scripts/ 안)
sys.path.insert(0, str(EXP / "scripts"))
import followup_simple as fs

TOPICS = "ABCDEFGHIJ"


def fake_embed(texts):
    """답변 문자열의 첫 글자(A~J)를 토픽으로 보고 원-핫 벡터를 돌려준다."""
    out = []
    for t in texts:
        v = [0.0] * len(TOPICS)
        v[TOPICS.index(t[0])] = 1.0
        out.append(v)
    return out


def mk(spec, gwanju=()):
    """spec: [(메인답변토픽, [꼬리답변토픽...]), ...] → items + meta"""
    items, cands = [], []
    for i, (mtop, ttops) in enumerate(spec):
        mq = f"M{i}({mtop})"
        items.append({"question": mq, "answer": f"{mtop} 메인답변 {i}",
                      "follow_ups": [{"question": f"T{i}{j}({tt})", "answer": f"{tt} 꼬리답변 {i}{j}"}
                                     for j, tt in enumerate(ttops)]})
        cands.append({"question": mq, "anchor_type": "관주" if mq in gwanju else "본문", "anchor_ok": True})
        for j, tt in enumerate(ttops):
            tq = f"T{i}{j}({tt})"
            cands.append({"question": tq, "anchor_type": "관주" if tq in gwanju else "본문", "anchor_ok": True})
    return items, {"candidates": cands}


def shape(items):
    return [(m["question"], [t["question"] for t in m["follow_ups"]]) for m in items]


def total(items):
    return sum(1 + len(m["follow_ups"]) for m in items)


FAILED = []


def check(name, got, want):
    ok = got == want
    print(f"{'  OK ' if ok else '  FAIL'} {name}")
    if not ok:
        print(f"        기대: {want}")
        print(f"        실제: {got}")
        FAILED.append(name)


print("=== 1. 겹침 없음 → 9개 그대로, 구조 유지 ===")
items, meta = mk([("A", ["B", "C"]), ("D", ["E", "F"]), ("G", ["H", "I"])])
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("개수 9 유지", total(out), 9)
check("구조 동일", shape(out), shape(items))
check("dropped_by_embed=0", m2["embed_gate"]["dropped_by_embed"], 0)

print("=== 2. 꼬리 두 개가 겹침 → 하나만 빠짐 ===")
items, meta = mk([("A", ["B", "C"]), ("D", ["B", "F"]), ("G", ["H", "I"])])
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("개수 8", total(out), 8)
check("메인 3가지 유지", len(out), 3)
check("나중 B 꼬리가 빠짐", shape(out), [("M0(A)", ["T00(B)", "T01(C)"]),
                                          ("M1(D)", ["T11(F)"]),
                                          ("M2(G)", ["T20(H)", "T21(I)"])])

print("=== 3. 메인이 다른 메인과 겹침 → 뒤 메인 잘리고 꼬리가 승격 ===")
items, meta = mk([("A", ["B", "C"]), ("A", ["E", "F"]), ("G", ["H", "I"])])
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("개수 8", total(out), 8)
check("M1 자리에 T10 승격", shape(out), [("M0(A)", ["T00(B)", "T01(C)"]),
                                          ("T10(E)", ["T11(F)"]),
                                          ("M2(G)", ["T20(H)", "T21(I)"])])
check("승격 1건 기록", len(m2["embed_gate"]["promoted"]), 1)

print("=== 4. 한 가지가 통째로 겹침 → 가지 자체가 사라짐(메인 2가지) ===")
items, meta = mk([("A", ["B", "C"]), ("A", ["B", "C"]), ("G", ["H", "I"])])
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("개수 6", total(out), 6)
check("메인 2가지", len(out), 2)
check("남은 구조", shape(out), [("M0(A)", ["T00(B)", "T01(C)"]), ("M2(G)", ["T20(H)", "T21(I)"])])

print("=== 5. 관주형 우선 유지 — 메인보다 관주 꼬리를 살린다 ===")
items, meta = mk([("A", ["B", "C"]), ("D", ["E", "F"]), ("G", ["H", "I"])], gwanju=())
# M1(D)와 T20을 같은 토픽으로 만들고 T20을 관주로 지정
items, meta = mk([("A", ["B", "C"]), ("D", ["E", "F"]), ("G", ["D", "I"])], gwanju=("T20(D)",))
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("개수 8", total(out), 8)
check("메인 M1이 잘리고 관주 꼬리 T20 생존 · T10 승격", shape(out),
      [("M0(A)", ["T00(B)", "T01(C)"]), ("T10(E)", ["T11(F)"]), ("M2(G)", ["T20(D)", "T21(I)"])])
check("관주 1개 유지", m2["embed_gate"]["gwanju_kept"], 1)

print("=== 6. 극단: 전부 같은 답 → 1개만 남음 ===")
items, meta = mk([("A", ["A", "A"]), ("A", ["A", "A"]), ("A", ["A", "A"])])
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("개수 1", total(out), 1)
check("메인 1가지·꼬리 0", shape(out), [("M0(A)", [])])

print("=== 7. 임베딩 실패 → 원본 그대로(아무것도 안 자름) ===")
def boom(texts):
    raise RuntimeError("API down")
items, meta = mk([("A", ["A", "C"]), ("D", ["E", "F"]), ("G", ["H", "I"])])
out, m2 = fs.apply_embed_gate(items, meta, boom)
check("원본 9개 유지", total(out), 9)
check("embed_gate 기록 없음", "embed_gate" in m2, False)

print("=== 8. 답변이 빈 게 있으면 관문 건너뜀(안전) ===")
items, meta = mk([("A", ["A", "C"]), ("D", ["E", "F"]), ("G", ["H", "I"])])
items[1]["answer"] = ""
out, m2 = fs.apply_embed_gate(items, meta, fake_embed)
check("원본 9개 유지", total(out), 9)

print()
print("모두 통과 ✅" if not FAILED else f"실패 {len(FAILED)}건 ❌ {FAILED}")
sys.exit(1 if FAILED else 0)
