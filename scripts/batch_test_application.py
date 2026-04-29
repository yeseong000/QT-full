"""
말씀 적용하기 프롬프트 반복 테스트 (로컬 전용, Git 제외 권장)

- 같은 본문으로 N회(기본 10회) AI 호출
- application 섹션만 수집/저장
- 자동 규칙 검사로 3개 버킷 분류: 괜찮은 / 애매한 / 별로인
- 최종 판단은 사람이 내리기 위한 보조 도구

사용법:
    python scripts/batch_test_application.py                 # 오늘 날짜, 10회
    python scripts/batch_test_application.py 5               # 5회
    python scripts/batch_test_application.py 10 2026-04-23   # 10회, 특정 날짜
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# generate_ai 모듈 재사용
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from generate_ai import load_qt_data, generate_real, log, today_str, KST


# ===== 규칙 검사 =====
# 하드 위반 = 자동으로 "별로인"
HARD_VIOLATIONS = {
    "강요성 어휘(베풀)": ["베풀"],
    "강요성 어휘(전하겠)": ["전하겠습니다"],
    "강요성 어휘(나누겠)": ["나누겠습니다"],
    "타인 대상(주변 사람)": ["주변 사람", "주변의 사람"],
    "타인 대상(이웃)": ["이웃에게", "이웃을"],
    "타인 대상(타인/남)": ["타인에게", "남에게", "다른 사람에게"],
    "인물 모방(마음을 배우)": ["마음을 배우"],
    "피상 비유": ["룻처럼", "보아스처럼", "나오미처럼"],
    "보편 문구(작은 일에도 감사)": ["작은 일에도 감사"],
    "보편 문구(말씀에 귀 기울)": ["말씀에 귀 기울"],
}

# 자기 낮춤 위반 키워드 — 본문 인용부의 "나/내"는 제외 필요
# (단순 부분문자열 검사로는 한계가 있어 토큰/경계 기반으로 별도 검사)
HUMILITY_TOKENS_BAD = ["나는 ", "내가 ", "내 ", "나의 ", "나에게", "나를", "내게"]

# 소프트 위반 = "애매한" 후보 (맥락 의존)
SOFT_VIOLATIONS = {
    "타인 언급(주변)": ["주변"],
    "타인 언급(이웃)": ["이웃"],
    "~처럼 사용": ["처럼"],
    "타인 태도 지향(~사랑하는 태도)": ["사랑하는 태도"],
    "위하여 기도": ["위해 기도", "위하여 기도"],
}


def _count_humility_violations(application: list) -> list:
    """자기 낮춤 위반(나/내 사용) 검출. 작은따옴표 내 본문 인용은 제외."""
    import re
    hits = []
    for idx, a in enumerate(application, 1):
        for field in ("statement", "detail"):
            text = a.get(field, "")
            # 작은따옴표 안의 본문 인용 제거 후 검사
            stripped = re.sub(r"'[^']*'", "", text)
            for token in HUMILITY_TOKENS_BAD:
                if token in stripped:
                    hits.append(f"{idx}번 {field}: '{token.strip()}'")
                    break
    return hits


def analyze(application: list) -> dict:
    """application 3개 묶음에 대한 규칙 검사 결과를 반환."""
    all_text = " ".join(
        (a.get("statement", "") + " " + a.get("detail", ""))
        for a in application
    )

    hard_hits = [name for name, kws in HARD_VIOLATIONS.items()
                 if any(kw in all_text for kw in kws)]
    soft_hits = [name for name, kws in SOFT_VIOLATIONS.items()
                 if any(kw in all_text for kw in kws)]

    # 자기 낮춤 위반 (하드)
    humility_violations = _count_humility_violations(application)
    if humility_violations:
        hard_hits.append(f"자기 낮춤 위반(나/내 사용): {humility_violations}")

    # 구조 규칙
    structural = []
    if len(application) != 3:
        structural.append(f"항목 개수 {len(application)} (3이어야 함)")
    else:
        if not application[0].get("statement", "").startswith("저는 오늘,"):
            structural.append('1번이 "저는 오늘,"으로 시작하지 않음')
        starts = [a.get("statement", "")[:6] for a in application]
        if len(set(starts)) < 3:
            structural.append(f"시작 구조 중복: {starts}")

    # ~처럼 개수 (최대 1 허용)
    cheorm_count = all_text.count("처럼")
    cheorm_flag = None
    if cheorm_count > 1:
        structural.append(f"'~처럼' {cheorm_count}회 (최대 1 허용)")

    # 버킷 판정
    if hard_hits or structural:
        bucket = "별로인"
    elif soft_hits:
        bucket = "애매한"
    else:
        bucket = "괜찮은"

    return {
        "bucket": bucket,
        "hard_hits": hard_hits,
        "soft_hits": soft_hits,
        "structural": structural,
        "cheorm_count": cheorm_count,
    }


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    date = sys.argv[2] if len(sys.argv) > 2 else today_str()

    log("=" * 60)
    log(f"반복 테스트 시작: {n}회, 날짜 {date}")
    log("=" * 60)

    try:
        qt_data = load_qt_data(date)
        log(f"본문: {qt_data['title']} ({qt_data['scripture_ref']})", "OK")
    except FileNotFoundError as e:
        log(str(e), "ERR")
        return 1

    runs = []
    total_cost_krw = 0.0
    for i in range(1, n + 1):
        log(f"--- 실행 {i}/{n} ---")
        try:
            ai_data, cost_info = generate_real(qt_data)
            application = ai_data.get("application", [])
            verdict = analyze(application)
            runs.append({
                "run": i,
                "bucket": verdict["bucket"],
                "verdict": verdict,
                "application": application,
                "cost_krw": cost_info["cost_krw"],
            })
            total_cost_krw += cost_info["cost_krw"]
            for j, a in enumerate(application, 1):
                print(f"  {j}. {a.get('statement', '')}")
                print(f"     └ {a.get('detail', '')}")
            print(f"  [{verdict['bucket']}] "
                  f"hard={verdict['hard_hits']} "
                  f"soft={verdict['soft_hits']} "
                  f"struct={verdict['structural']}")
        except Exception as e:
            log(f"실행 {i} 실패: {e}", "ERR")
            runs.append({"run": i, "bucket": "에러", "error": str(e)})

    # ===== 버킷별 정리 =====
    buckets = {"괜찮은": [], "애매한": [], "별로인": [], "에러": []}
    for r in runs:
        buckets.setdefault(r.get("bucket", "에러"), []).append(r)

    print()
    log("=" * 60)
    log("버킷별 요약")
    log("=" * 60)
    for name in ["괜찮은", "애매한", "별로인", "에러"]:
        log(f"{name}: {len(buckets[name])}개")
    log(f"총 비용: 약 {total_cost_krw:.1f}원")

    # ===== 저장 =====
    now = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    out_path = SCRIPT_DIR.parent / "data" / f"application_test_{date}_{now}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({
            "date": date,
            "scripture_ref": qt_data["scripture_ref"],
            "title": qt_data["title"],
            "runs": runs,
            "buckets": {k: [r["run"] for r in v] for k, v in buckets.items()},
            "total_cost_krw": round(total_cost_krw, 2),
            "generated_at": datetime.now(KST).isoformat(),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"로그 저장: {out_path}", "OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
