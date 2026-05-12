# 🎯 NEXT_STEPS.md - 앞으로 할 작업

**마지막 업데이트**: 2026-04-22
**현재 단계**: Phase 3 일부 완료 (홈 + 1단계 화면)

---

## 📊 진행률 대시보드

```
Phase 0: 문서 세팅              ██████████ 100% ✅
Phase 1: 크롤러 (fetch_qt.py)   ██████████ 100% ✅ (로컬 테스트 필요)
Phase 2: AI 묵상 (generate_ai)  ██████████ 100% ✅ (로컬 테스트 필요)
Phase 3: 프론트엔드             ███░░░░░░░  30% 🔄 진행 중
Phase 4: 자동화 + 배포          ░░░░░░░░░░   0% ⏳
Phase 5: PWA 고도화             ░░░░░░░░░░   0% ⏳
```

**전체**: 약 45% 완료

---

## 🥇 Phase 3 - 남은 프론트엔드 (최우선)

### ✅ 완료된 것

- [x] 디자인 시스템 (`design-tokens.css`, `common.css`)
- [x] 컴포넌트 갤러리 (`preview.html`)
- [x] 홈 화면 (`index.html`)
  - [x] 시간대별 인사말
  - [x] 닉네임 "어린양님" (설정 변경)
  - [x] 스트릭 카드
  - [x] 오늘의 말씀 카드
  - [x] ⚙️ 설정 모달
- [x] 1단계: 말씀 (`step-1-scripture.html`)
  - [x] 성경 본문 렌더링
  - [x] 폰트 크기 조절
  - [x] 진행 단계 표시
- [x] iPhone 14/15 Pro 최적화
  - [x] 세이프 에어리어
  - [x] PC iPhone 프레임
  - [x] PWA 메타태그

### 🔜 해야 할 것

#### 3-1. 2단계: 묵상 화면
**파일**: `src/step-2-meditation.html`

- [ ] `data/ai/YYYY-MM-DD.json` 로드
- [ ] 상단 **말씀 토글** (접혀있다가 탭 시 펼침)
  - [ ] 제목 영역: `📖 룻기 1:15-22 ▼` 형태
  - [ ] 펼쳐지면 전체 본문 표시
  - [ ] sticky 상단 고정
- [ ] **핵심 요약 카드** (5줄 불릿)
- [ ] **등장인물 카드** (1~3명)
- [ ] **책 맥락 카드** (책 전체 흐름)
- [ ] **구절 해설 카드**
- [ ] 하단 네비 (이전 → 1단계, 다음 → 3단계)

**데이터 경로**:
```javascript
const ai = await Common.loadJSON('../data/ai/2026-04-22.json');
// ai.core_summary, ai.characters, ai.book_context, ai.verse_commentary
```

#### 3-2. 3단계: 적용+기도 화면
**파일**: `src/step-3-prayer.html`

- [ ] **적용하기 카드**
  - [ ] `ai.application[]` 3개 렌더링
  - [ ] 각 항목: `statement` + `detail`
- [ ] **기도문 카드**
  - [ ] `ai.prayer[]` 줄 단위 렌더링 (시적 줄바꿈 유지)
  - [ ] 빈 줄(`""`)은 간격만 표시
  - [ ] 🙏 "기도했어요" 버튼 (토글)
  - [ ] 기도 완료 시 localStorage `records.{date}.prayed = true`
- [ ] 하단 네비 (이전 → 2단계, 다음 → 4단계)

#### 3-3. 4단계: 감정+메모 화면
**파일**: `src/step-4-record.html`

- [ ] **감정 칩 카드** (9개 칩, 다중 선택)
  - [ ] 칩 데이터는 `common.js`에 상수로 관리
  - [ ] 선택 시 `records.{date}.emotions` 배열에 저장
- [ ] **메모 카드**
  - [ ] textarea (자동 리사이즈)
  - [ ] 최대 500자 (카운터 표시)
  - [ ] 입력 중 자동 저장 (debounce 1초)
- [ ] 하단 네비 (이전 → 3단계, **완료하기** → 5단계)
- [ ] 완료 버튼 클릭 시:
  - [ ] `Storage.markCompleted()` 호출 (연속일 +1)
  - [ ] `records.{date}.completed = true` 저장
  - [ ] 5단계로 이동

#### 3-4. 완료 축하 화면
**파일**: `src/step-5-done.html`

- [ ] 🎉 "오늘도 수고하셨어요!" 인사
- [ ] 연속일 달성 시각화 (14일 → 15일)
- [ ] 마일스톤 체크 (10/30/100일 특별 메시지)
- [ ] **오늘의 내 밑줄** 섹션 (밑줄 기능 완성 후)
- [ ] 버튼:
  - [ ] "지난 묵상 아카이브 보기"
  - [ ] "홈으로 돌아가기"

#### 3-5. 아카이브 페이지
**파일**: `src/archive.html`

- [ ] 월별 그룹핑 리스트
- [ ] 각 항목: 날짜 + 구절 + 제목 + 내 감정칩
- [ ] 탭하면 해당 날짜 묵상 재열람
- [ ] 데이터: `Object.keys(localStorage)` 중 `records.` 필터링

---

## 🥈 Phase 4 - 자동화 + 배포

### 4-1. 크롤러 로컬 테스트
- [ ] 프로젝트 루트에서 `pip install -r scripts/requirements.txt`
- [ ] `python scripts/fetch_qt.py --dry-run` 실행
- [ ] 성공 시 실제 실행으로 `data/qt/YYYY-MM-DD.json` 생성
- [ ] 여러 날짜 테스트 (주말 포함)
- [ ] 403 에러 시 `scripts/fetch_qt.py`의 헤더 조정

### 4-2. AI 생성 로컬 테스트
- [ ] OpenAI API 키 발급 (https://platform.openai.com)
- [ ] `.env.example` 복사 → `.env` 생성
- [ ] `.env`에 API 키 붙여넣기
- [ ] `python scripts/generate_ai.py --mock` (먼저 Mock 테스트)
- [ ] `python scripts/generate_ai.py` (실제 API 호출)
- [ ] 비용 확인 (약 1.5원 / 회)

### 4-3. GitHub Actions 자동화
**파일**: `.github/workflows/daily_qt.yml`

- [ ] Workflow YAML 작성
- [ ] `cron: '0 20 * * *'` (KST 05:00 = UTC 20:00)
- [ ] Steps:
  - [ ] checkout
  - [ ] Python setup
  - [ ] `pip install -r scripts/requirements.txt`
  - [ ] `python scripts/fetch_qt.py`
  - [ ] `python scripts/generate_ai.py`
  - [ ] `git commit && git push` (변경된 JSON)
- [ ] GitHub Repository Secrets 등록:
  - [ ] `OPENAI_API_KEY`
- [ ] 수동 실행 버튼 추가 (`workflow_dispatch`)
- [ ] 실제 스케줄 동작 확인 (1~2일 관찰)

### 4-4. Vercel 배포
- [ ] Vercel 계정 가입 (https://vercel.com)
- [ ] GitHub 리포지토리 연결
- [ ] 빌드 설정:
  - [ ] Framework: Other / Static
  - [ ] Root Directory: `/`
  - [ ] Output: 그대로
- [ ] `vercel.json` 작성 (필요 시)
  - [ ] `src/index.html`을 루트로 설정
  - [ ] SPA 라우팅 (선택)
- [ ] 커스텀 도메인 연결 (선택)
- [ ] 프로덕션 URL에서 iPhone 접속 테스트

---

## 🥉 Phase 5 - PWA 고도화

### 5-1. Manifest
**파일**: `src/manifest.json`

- [ ] 앱 이름: "주만나 AI 큐티"
- [ ] short_name: "주만나"
- [ ] 테마 컬러: `#F7F4ED`
- [ ] 배경: `#F7F4ED`
- [ ] display: `standalone`
- [ ] start_url: `/src/index.html`
- [ ] 아이콘 연결 (아래 참조)

### 5-2. 앱 아이콘
**디렉토리**: `src/assets/icons/`

- [ ] 원본 아이콘 디자인 (1024×1024)
  - [ ] 세이지 그린 배경 + 어린양/잎 심볼
- [ ] 사이즈별 생성:
  - [ ] 192×192 (Android)
  - [ ] 512×512 (Android)
  - [ ] 180×180 (iOS apple-touch-icon)
  - [ ] 167×167, 152×152 (iPad)
- [ ] 각 HTML에 `<link>` 태그 추가

### 5-3. Service Worker (오프라인 캐싱)
**파일**: `src/sw.js`

- [ ] 캐시 전략: 앱쉘 캐싱 + 네트워크 우선
- [ ] 캐시할 파일:
  - [ ] HTML/CSS/JS
  - [ ] 최근 7일 QT JSON
- [ ] `install` → 초기 캐시
- [ ] `fetch` → 오프라인 시 캐시 응답
- [ ] `activate` → 오래된 캐시 정리
- [ ] 각 HTML에서 SW 등록 코드 추가

### 5-4. 설정 화면 고도화
**파일**: `src/settings.html` (선택, 모달 확장 가능)

- [ ] 🎨 테마 (라이트/다크)
- [ ] 🖼️ 배경 이미지 선택
  - [ ] `/public/assets/backgrounds/` 폴더 구조 마련
  - [ ] `backgrounds.json` 메타데이터 파일
- [ ] 🔤 폰트 크기 설정 UI
- [ ] 💾 데이터 내보내기 (JSON 다운로드)
- [ ] 🗑️ 데이터 초기화 (2단계 확인)

### 5-5. 다크모드 구현
- [ ] `design-tokens.css`의 `[data-theme="dark"]` 토큰 확인
- [ ] 시스템 설정 연동 (`prefers-color-scheme`)
- [ ] 설정에서 수동 전환
- [ ] 이미지/그라디언트 다크 버전 확인

---

## 🔮 Phase 6 - 확장 기능 (선택)

### 기능별 우선순위

| 우선순위 | 기능 | 난이도 |
|---|---|---|
| High | 밑줄 실제 저장 기능 | 중 |
| High | 밑줄 모음 페이지 | 하 |
| Mid | 연속일 마일스톤 축하 | 하 |
| Mid | 감정 통계 (월별) | 중 |
| Mid | 월별 묵상 요약 | 중 |
| Low | 배경 찬양 BGM | 중 |
| Low | 번역본 전환 (NIV 등) | 상 |
| Low | 이미지로 공유 | 중 |
| Low | 검색 기능 | 중 |
| Low | TTS (성경 낭독) | 중 |

---

## 📌 작업 순서 추천

### Week 1 (프론트 완성)
1. Day 1-2: 2단계 묵상 화면
2. Day 3: 3단계 적용+기도 화면
3. Day 4: 4단계 감정+메모 화면
4. Day 5: 5단계 완료 화면 + 아카이브

### Week 2 (배포 준비)
1. Day 1: 크롤러/AI 로컬 테스트
2. Day 2: GitHub Repo + Actions
3. Day 3: Vercel 배포
4. Day 4-5: iPhone 실제 테스트 + 버그 수정

### Week 3 (PWA)
1. Day 1-2: Manifest + 아이콘
2. Day 3: Service Worker
3. Day 4-5: 설정 고도화 + 다크모드

### Week 4+ (확장)
- 필요한 기능 선별적으로 구현
- 실제 사용 피드백 반영

---

## 🎯 각 작업별 Claude Code 요청 템플릿

### 새 화면 만들 때
```
docs/USER_FLOW.md의 [N단계] 부분을 참고하고,
src/step-1-scripture.html의 구조/패턴을 따라서
src/step-N-xxx.html을 만들어줘.

데이터는 data/ai/2026-04-22.json을 로드하고,
design-tokens.css의 색상/간격을 그대로 사용해.
```

### 디자인 수정할 때
```
docs/DESIGN_TOKENS.md 기준으로,
src/styles/common.css의 [컴포넌트명] 부분을 수정해줘.
[수정 내용 구체적으로]
```

### 기능 추가할 때
```
docs/DATA_SCHEMA.md의 [항목] 부분을 참고하고,
src/scripts/storage.js에 [함수명] 추가해줘.
사용 예: [예시 코드]
```

---

## ⚠️ 주의사항 & 알려진 이슈

- **오륜교회 서버 403 이슈**: Claude 샌드박스 환경에서는 차단. 로컬/GitHub Actions에서는 대부분 정상.
- **API 키 보안**: `.env` 파일은 절대 커밋 금지 (이미 `.gitignore` 포함)
- **데이터 경로**: HTML은 `../data/qt/...` 상대 경로 사용. 프로젝트 루트에서 서버 실행 필수.
- **localStorage 의존**: 브라우저 캐시 삭제 시 데이터 소실. "내보내기" 기능 빨리 구현 권장.
- **JSON 파일명**: `YYYY-MM-DD.json` 엄격히 준수 (날짜 로직이 이 형식 기반).

---

## 📞 다시 시작할 때 체크리스트

VS Code 또는 Claude Code에서 이 프로젝트 다시 열었을 때:

- [ ] `docs/README.md` 읽기 (전체 개요)
- [ ] `CONTEXT.md` 읽기 (현재 상태)
- [ ] `NEXT_STEPS.md` 읽기 (이 문서)
- [ ] `python3 -m http.server 8000` 실행
- [ ] http://localhost:8000/src/index.html 동작 확인
- [ ] 어디서부터 이어갈지 결정 (위 Phase 순서 참고)
