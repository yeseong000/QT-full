# 📜 Scripts 가이드

주만나 QT 자동화 스크립트 모음입니다.

---

## 📦 설치

```bash
# 1. 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate   # macOS/Linux
# 또는
venv\Scripts\activate      # Windows

# 2. 의존성 설치
pip install -r scripts/requirements.txt
```

---

## 🚀 사용법

### 1. 오늘 QT 크롤링

```bash
python scripts/fetch_qt.py
```

결과: `data/qt/YYYY-MM-DD.json` 파일 생성

### 2. 드라이런 (저장 없이 결과만 확인)

```bash
python scripts/fetch_qt.py --dry-run
```

### 3. 저장 경로 지정

```bash
python scripts/fetch_qt.py --output data/qt/test.json
```

---

## 🎯 예상 출력

```
[07:00:01] ℹ️  ==================================================
[07:00:01] ℹ️  주만나 QT 크롤링 시작
[07:00:01] ℹ️  ==================================================
[07:00:01] ℹ️  메인 페이지 방문 중...
[07:00:02] ℹ️  QT 페이지 요청 중 (시도 1/3)...
[07:00:03] ✅ 응답 수신 완료 (156,789 bytes)
[07:00:03] ✅ 날짜 레이블: 04.22수요일
[07:00:03] ✅ 제목: 회복으로 나아가라
[07:00:03] ✅ 구절: 룻기 1:15-22
[07:00:03] ℹ️  부제: 나오미와 함께 가기로 결심한 룻
[07:00:03] ✅ 구절 추출: 8절
[07:00:03] ℹ️  질문 추출: 2개
[07:00:03] ✅ 저장 완료: data/qt/2026-04-22.json
[07:00:03] ℹ️  ==================================================
[07:00:03] ℹ️  제목:   회복으로 나아가라
[07:00:03] ℹ️  구절:   룻기 1:15-22
[07:00:03] ℹ️  절 수:  8
[07:00:03] ℹ️  질문:   2개
[07:00:03] ℹ️  ==================================================
```

---

## 🐛 문제 해결

### `403 Forbidden` 에러

오륜교회 서버가 특정 IP/User-Agent를 차단했을 수 있습니다.

**해결 방법**:
1. VPN을 사용 중이라면 끄고 재시도
2. 다른 네트워크(모바일 테더링 등)에서 시도
3. 시간을 두고 재시도
4. GitHub Actions 환경은 클라우드 IP라 보통 문제없이 동작

### `파싱 실패` 에러

오륜교회 사이트의 HTML 구조가 변경되었을 가능성이 있습니다.

**해결 방법**:
1. https://oryun.org/life/?menu=248 에 직접 접속해서 확인
2. `parse_qt()` 함수의 셀렉터 수정 필요
3. Issue 제보 (프로젝트 리포지토리)

### `구절 개수 불일치` 경고

페이지에서 일부 구절을 추출하지 못했을 때 발생. 심각하지 않으면 그대로 저장됩니다.

---

## 🧪 로컬 테스트 체크리스트

처음 실행 시 아래 순서로 확인:

- [ ] `pip install -r requirements.txt` 정상 완료
- [ ] `python scripts/fetch_qt.py --dry-run` 실행 시 JSON 출력됨
- [ ] `python scripts/fetch_qt.py` 실행 시 `data/qt/` 폴더에 파일 생성됨
- [ ] 생성된 JSON을 열어봤을 때 오늘 QT 내용이 정확히 들어있음
- [ ] 구절 개수가 `verses_end - verses_start + 1` 과 일치

---

## 🔜 다음 단계

- `generate_ai.py`: AI 묵상 생성 스크립트 ✅ **완료!**
- `.github/workflows/daily_qt.yml`: 매일 새벽 자동 실행 (Phase 4)

---

## 🤖 generate_ai.py - AI 묵상 생성

### 사전 준비

```bash
# 1. .env.example을 복사해서 .env 만들기
cp .env.example .env

# 2. .env 파일 열어서 API 키 넣기
# OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 사용법

```bash
# Mock 모드 (API 호출 없이 샘플 응답 - 개발/테스트용)
python scripts/generate_ai.py --mock

# 실제 모드 (.env 의 API 키 사용)
python scripts/generate_ai.py

# 특정 날짜 지정
python scripts/generate_ai.py --date 2026-04-22

# 드라이런 (저장 없이 결과만 출력)
python scripts/generate_ai.py --mock --dry-run
```

### 예상 출력 (실제 모드)

```
[07:00:05] ℹ️  AI 묵상 생성 시작 (날짜: 2026-04-22, 모드: Real)
[07:00:05] ✅ QT 데이터 로드: 회복으로 나아가라 (룻기 1:15-22)
[07:00:05] ℹ️  OpenAI API 호출 중 (모델: gpt-4o-mini)...
[07:00:08] ✅ 토큰: 1423(입력) + 1587(출력) = 3010
[07:00:08] ✅ 비용: $0.001103 (약 1.49원)
[07:00:08] ✅ 검증 통과 ✓
[07:00:08] ✅ 저장 완료: data/ai/2026-04-22.json
```

### 비용 안내

| 구분 | 토큰 | 비용 (USD) | 비용 (KRW) |
|---|---|---|---|
| 입력 | ~1,500 | $0.000225 | ~0.3원 |
| 출력 | ~1,500 | $0.000900 | ~1.2원 |
| **합계** | ~3,000 | **$0.001** | **~1.5원** |

→ **1년 사용해도 약 550원** 수준입니다.

### 검증 로직

`AI_PROMPT.md`의 요구사항을 자동 체크합니다:

- ✓ `core_summary` 정확히 5줄
- ✓ `characters` 1~3명
- ✓ `application` 정확히 3개
- ✓ `prayer` 8~14줄
- ✓ 금지어 포함 여부 (`여러분`, `~해야만` 등)

검증 실패 시 경고 출력 (저장은 계속 진행). 심각한 경우 수동 재실행 권장.

### 🔒 보안 주의사항

- **`.env` 파일은 절대 Git에 커밋하지 마세요** (`.gitignore`에 이미 포함)
- **API 키는 대화창/채팅에도 붙여넣지 마세요**
- GitHub Actions에서는 **Repository Secrets**에 등록해서 사용
