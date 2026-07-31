"""떠오르는 질문 — '진짜 중복' 측정기.  ※ 운영 아님, _접두사=미커밋 로컬 도구.

배경(2026-07-17 조사, 떠오르는질문_중복_근본원인_조사_0717.html):
  - `_followup_meta.distinct_knowledge_in_final`(distinct 9/9)은 **가짜 지표**다.
    판정 모델(mini)이 겹침을 못 찾으면 전부 고유 클러스터가 되어 가짜 9/9가 찍힌다.
  - `topic` 라벨 유일성도 **가짜 지표**다. 라벨만 다르고 알맹이는 하나.

2026-07-19 개정 — 자카드(단어 겹침)도 단독으로는 못 믿는다:
  7/19는 자카드 0건·최고 0.00으로 '깨끗' 판정을 받았지만, 실제로는 6절 하나에
  질문 3개가 몰려 있었다(①아람 배경 ↔ ③벧르홉·소바 역할 = 사실상 같은 답, 자카드 0.183).
  같은 사실을 다른 어휘로 쓰면 단어가 안 겹치기 때문이다. 이건 임계값 문제가 아니라
  방법의 한계다 — 문헌에서 'fast car' vs 'quick automobile'로 알려진 교과서적 실패다
  (MinHash/자카드류는 철자만 보고 의미를 못 본다. SemDeDup·SemHash가 존재하는 이유).

그래서 이 측정기는 **세 잣대를 나란히** 본다. 하나라도 걸리면 의심한다:
  ① 임베딩 코사인 (주력) — 뜻으로 본다. 어휘를 바꿔도 안 뚫린다.
  ② 자카드 단어 겹침 (보조) — 옛 기록과 비교용. 놓치는 게 있다는 걸 알고 쓴다.
  ③ 절 겹침 (공짜·결정론) — 같은 절에 몰렸는가. 모델 판단이 아니라 코드가 본문과 대조한 값.

임계값은 '민담'이다(0.85 같은 숫자는 모델마다 다르다). --calibrate로 직접 라벨링한
쌍에 대고 맞춰라. 아래 기본값은 이 저장소 데이터로 보정한 값이다.

비용: text-embedding-3-small = $0.02/1M토큰. 하루 9개 답변 ≈ 0.0000?달러(사실상 0원).
      한 번 부른 임베딩은 _embed_cache.json에 저장해 재실행은 완전 무료다.

사용:
  python scripts/_measure_answer_overlap.py 2026-07-16     # 한 날짜 상세
  python scripts/_measure_answer_overlap.py --all           # 전체 훑기(요약)
  python scripts/_measure_answer_overlap.py --calibrate     # 임계값 보정용 쌍 목록 출력
  python scripts/_measure_answer_overlap.py path/to/ab.json # 임의 결과 파일(A/B 산출물 등)
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEEP = REPO / "data" / "deep_dive"
QT = REPO / "data" / "qt"
CACHE = Path(__file__).resolve().parent / "_embed_cache.json"

EMBED_MODEL = "text-embedding-3-small"

# 이 저장소 데이터(2844쌍)로 보정한 값 — --calibrate로 재현된다. 모델을 바꾸면 다시 보정할 것.
#
# ★ 이건 '판결'이 아니라 '선별 그물'이다. 보정해보니 진짜 겹침과 오탐 구간이 겹친다:
#     0.95 7/16 '영원히' 두 질문            → 진짜 겹침
#     0.85 7/14 '베 에봇' 두 질문           → 진짜 겹침
#     0.82 7/19 암몬 전술 ↔ 성문 어귀 진    → 진짜 겹침
#     0.81 '깊은 잠' 히브리어 ↔ 다른 용례   → 애매(어원 vs 상호참조)
#     0.80 엘리가 숨기지 말라 ↔ 사무엘의 말 → 오탐에 가까움
#     0.79 벧세메스에서 들여다봄 ↔ 기럇여아림으로 옮김 → 오탐(다른 사건)
#     0.76 7/19 아람 배경 ↔ 벧르홉·소바 역할 → 진짜 겹침 (자카드는 0.18로 놓쳤다)
# 즉 진짜(0.76)가 오탐(0.79)보다 낮은 구간이 실제로 존재한다. 깔끔한 경계선은 없다.
# 그래서 놓치는 쪽보다 과잉 신고하는 쪽으로 잡는다 — 걸린 건 사람이 보고 판단한다.
# 예방은 이 잣대가 아니라 '절·anchor 자리 배정'(followup_simple.py)이 담당한다.
SIM_THRESHOLD = 0.75   # 임베딩 코사인: 이 이상이면 '사람이 확인해봐야 할 쌍'
THRESHOLD = 0.30       # 자카드(보조 지표). 옛 기록과 비교하려고 남겨둔다.

# 답변에 흔해서 소재 구분에 도움 안 되는 단어(불용어). 이게 겹친다고 같은 지식은 아니다.
STOP = set(
    "그리고 그러나 하지만 이는 이것은 그것은 있어요 있었어요 했어요 해요 이에요 예요 "
    "통해 대한 위해 그의 그를 그가 이런 이러한 때문 여기 저기 또한 그래서 그런 모든 "
    "매우 정말 바로 특히 다시 함께 서로 각각 이제 당시 사람 사람들 우리 자신 하나님 "
    "여호와 다윗 이스라엘".split()
)


def words(t: str) -> set:
    return {w for w in re.findall(r"[가-힣]{2,}", t or "") if w not in STOP}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


# ===== 임베딩 (캐시됨 — 같은 문장은 두 번 부르지 않는다) =====
def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _key(t: str) -> str:
    return hashlib.sha1(f"{EMBED_MODEL}:{t}".encode("utf-8")).hexdigest()


def embed_all(texts: list) -> list:
    """문장 리스트 → 벡터 리스트. 캐시에 없는 것만 API로 부른다."""
    cache = _load_cache()
    todo = [t for t in texts if _key(t) not in cache]
    if todo:
        try:
            from openai import OpenAI
        except ImportError:
            raise SystemExit("openai 패키지가 필요합니다: pip install openai")
        try:
            from dotenv import load_dotenv
            load_dotenv(REPO / ".env")
        except ImportError:
            pass
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("OPENAI_API_KEY가 없습니다(.env 확인).")
        client = OpenAI(api_key=api_key)
        for i in range(0, len(todo), 100):
            batch = todo[i:i + 100]
            resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
            for t, item in zip(batch, resp.data):
                cache[_key(t)] = item.embedding
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return [cache[_key(t)] for t in texts]


def cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


# ===== 한 날짜 읽기 =====
def _flatten(data: dict) -> list:
    """{'question','answer','verse','anchor'} 9개."""
    anchors = {}
    for c in ((data.get("_followup_meta") or data.get("meta") or {}).get("candidates") or []):
        if c.get("selected"):
            anchors[c.get("question")] = (c.get("verse"), c.get("anchor"), c.get("anchor_ok"))
    out = []
    for m in (data.get("follow_up_questions") or data.get("items") or []):
        for q in [m] + (m.get("follow_ups") or []):
            v, a, ok = anchors.get(q.get("question"), (None, None, None))
            out.append({"question": q.get("question", ""), "answer": q.get("answer", ""),
                        "verse": v, "anchor": a, "anchor_ok": ok})
    return out


def load(label_or_path):
    p = Path(label_or_path)
    if p.suffix == ".json" and p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        return p.stem, data
    d = DEEP / f"{label_or_path}.json"
    if not d.exists():
        raise SystemExit(f"없는 날짜/파일: {label_or_path}")
    return label_or_path, json.loads(d.read_text(encoding="utf-8"))


def analyze(label_or_path) -> dict:
    label, data = load(label_or_path)
    qs = _flatten(data)
    meta = data.get("_followup_meta") or data.get("meta") or {}
    answers = [q["answer"] for q in qs]
    vecs = embed_all(answers) if any(answers) else []
    wsets = [words(a) for a in answers]

    pairs = []
    for i in range(len(qs)):
        for j in range(i + 1, len(qs)):
            sim = cosine(vecs[i], vecs[j]) if vecs else 0.0
            jac = jaccard(wsets[i], wsets[j])
            same_verse = (qs[i]["verse"] is not None and qs[i]["verse"] == qs[j]["verse"])
            pairs.append({"i": i, "j": j, "sim": sim, "jac": jac, "same_verse": same_verse})
    pairs.sort(key=lambda p: -p["sim"])

    verses = [q["verse"] for q in qs if q["verse"] is not None]
    return {
        "label": label, "qs": qs, "pairs": pairs, "meta": meta,
        "sim_flagged": [p for p in pairs if p["sim"] >= SIM_THRESHOLD],
        "jac_flagged": [p for p in pairs if p["jac"] >= THRESHOLD],
        "verse_flagged": [p for p in pairs if p["same_verse"]],
        "max_sim": max((p["sim"] for p in pairs), default=0.0),
        "max_jac": max((p["jac"] for p in pairs), default=0.0),
        "distinct_verses": len(set(verses)) if verses else None,
        "recorded_distinct": meta.get("distinct_knowledge_in_final"),
    }


def print_one(r, verbose=True):
    ns, nj, nv = len(r["sim_flagged"]), len(r["jac_flagged"]), len(r["verse_flagged"])
    dv = r["distinct_verses"]
    dv_s = f"{dv}/9" if dv is not None else "—"
    flag = "⚠️ 의심" if (ns or nj or nv) else "✅ 깨끗"
    print(f"[{r['label']}] 뜻겹침 {ns}건(최고 {r['max_sim']:.2f}) · "
          f"단어겹침 {nj}건(최고 {r['max_jac']:.2f}) · 같은절 {nv}건 · 서로 다른 절 {dv_s}  {flag}")
    if r["jac_flagged"] and not r["sim_flagged"]:
        print("      ↑ 단어만 겹치고 뜻은 다름(오탐 가능)")
    if r["sim_flagged"] and not r["jac_flagged"]:
        print("      ↑ 단어는 안 겹치는데 뜻이 겹침 — 자카드가 놓치던 바로 그 유형")
    if not verbose:
        return
    qs = r["qs"]
    shown = {(p["i"], p["j"]) for p in r["sim_flagged"] + r["jac_flagged"] + r["verse_flagged"]}
    for p in r["pairs"]:
        if (p["i"], p["j"]) not in shown:
            continue
        tags = []
        if p["sim"] >= SIM_THRESHOLD:
            tags.append("뜻")
        if p["jac"] >= THRESHOLD:
            tags.append("단어")
        if p["same_verse"]:
            tags.append(f"{qs[p['i']]['verse']}절")
        print(f"   [{'+'.join(tags)}] 뜻 {p['sim']:.2f} · 단어 {p['jac']:.2f}")
        print(f"      · {qs[p['i']]['question']}")
        print(f"      · {qs[p['j']]['question']}")


def calibrate():
    """모든 날짜의 모든 쌍을 유사도 순으로 출력 — 눈으로 보고 임계값을 정하라."""
    rows = []
    for d in sorted(DEEP.glob("*.json")):
        try:
            r = analyze(d.stem)
        except SystemExit:
            continue
        for p in r["pairs"]:
            rows.append((p["sim"], p["jac"], r["label"], r["qs"][p["i"]]["question"],
                         r["qs"][p["j"]]["question"]))
    rows.sort(reverse=True)
    print(f"전체 쌍 {len(rows)}개 — 상위 25개(여기서 '진짜 겹침'이 끝나는 지점이 임계값)")
    print(f"{'뜻':>5s} {'단어':>5s}  날짜")
    for sim, jac, label, q1, q2 in rows[:25]:
        print(f"{sim:5.2f} {jac:5.2f}  [{label}]")
        print(f"              · {q1}")
        print(f"              · {q2}")


def main():
    args = [a for a in sys.argv[1:]]
    if "--calibrate" in args:
        calibrate()
        return 0
    if "--all" in args or not args:
        results = []
        for d in sorted(DEEP.glob("*.json")):
            try:
                r = analyze(d.stem)
            except SystemExit:
                continue
            results.append(r)
            print_one(r, verbose=False)
        bad = [r for r in results if r["sim_flagged"] or r["jac_flagged"] or r["verse_flagged"]]
        missed = [r["label"] for r in results if r["sim_flagged"] and not r["jac_flagged"]]
        print(f"\n의심 발생일 {len(bad)}/{len(results)}건"
              + (f" · 그중 자카드가 놓쳤을 날 {len(missed)}건: {missed}" if missed else ""))
        return 0
    for a in args:
        print_one(analyze(a))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
