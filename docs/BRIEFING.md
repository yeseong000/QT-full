# 📨 BRIEFING.md — Claude 웹 전달용 1페이지 브리핑

> **이 문서의 용도**: Claude 웹(또는 새로운 AI 세션)에 프로젝트를 처음 설명할 때 **첫 메시지에 복붙**하세요. 이것만 읽어도 AI가 프로젝트의 정체성/현황/제약을 파악할 수 있도록 설계되었습니다.

---

## 1️⃣ 프로젝트 정체성 (한 문단 요약)

**이름**: 주만나 AI 큐티 (Jumanna AI QT)
**장르**: 개인용 성경 묵상 모바일 웹 앱 (PWA)
**사용자**: 나 1명 (개발자 본인, 비전공 바이브 코더)
**사용 맥락**: 매일 아침 iPhone에서 3~5분, 출근 전 묵상
**한 줄 컨셉**: 오륜교회 주만나 본문을 **매일 새벽 5시** 자동으로 가져오고 → GPT가 **개인화된 묵상 가이드**를 생성하고 → **4단계 가이드형 UI**로 차분하게 묵상

---

## 2️⃣ 왜 만드는가 (철학)

| 가치 | 의미 |
|---|---|
| **가벼움** | 과하지 않게. 3~5분에 끝나는 아침 루틴 |
| **자동화** | 사용자는 아무것도 안 해도 매일 QT가 준비됨 |
| **분위기** | "잔디밭 오후 + 미니멀" — 정적, 따뜻함, 세이지 그린 |
| **기록** | 밑줄·메모·감정이 쌓여 성장감을 느낌 |

> **말투 원칙**: 설교조 금지, 훈계 금지, 과한 이모지 금지. **짧고 따뜻한 문장**.

---

## 3️⃣ 현재 상태 (2026-04-22 기준, 약 45% 완료)

### ✅ 이미 구현됨
- 디자인 시스템 (`design-tokens.css`, `common.css`)
- 홈 화면 (`src/index.html`) — 인사말, 스트릭, 오늘의 말씀, 설정 모달
- 1단계 말씀 화면 (`src/step-1-scripture.html`)
- Python 크롤러 (`scripts/fetch_qt.py`)
- Python AI 생성기 (`scripts/generate_ai.py`, Mock 동작 확인)
- 샘플 데이터 (`data/qt/2026-04-22.json`, `data/ai/2026-04-22.json`)
- iPhone 14/15 Pro 최적화 + PC iPhone 프레임

### 🔜 남은 작업
- 2~5단계 화면 (묵상/적용+기도/감정+메모/완료)
- 아카이브 페이지
- GitHub Actions 자동화 (매일 05:00 KST cron)
- Vercel 배포
- PWA (Manifest + Service Worker + 아이콘)
- **일본어 현지화** (`JAPANESE_LOCALIZATION_PLAN.md` 별도 존재)

---

## 4️⃣ 기술 스택 & 아키텍처

```
[매일 05:00 KST - GitHub Actions]
  │
  ├─ fetch_qt.py (BeautifulSoup) → data/qt/YYYY-MM-DD.json
  │
  └─ generate_ai.py (OpenAI GPT-4o-mini) → data/ai/YYYY-MM-DD.json
         │
         ▼
  git commit & push
         │
         ▼
[Vercel 정적 호스팅]
         │
         ▼
  iPhone → src/index.html
         │
         ├─ fetch(data/*.json)
         └─ localStorage (스트릭·메모·감정·밑줄)
```

**스택**:
- 프론트: **Vanilla JS** + 커스텀 CSS (React/Vue/Tailwind 사용 안 함)
- 백엔드: Python 3.9+ (BeautifulSoup, Requests, OpenAI SDK)
- 저장: localStorage (개인용이라 서버 DB 없음)
- 인증: 닉네임 입력만 (기본 "어린양님")
- 배포: Vercel (정적 호스팅)
- 자동화: GitHub Actions

---

## 5️⃣ 디자인 시스템 (꼭 지킬 것)

**테마**: 🌿 잔디밭 오후 + 미니멀

| 항목 | 값 |
|---|---|
| 메인 배경 | `#F7F4ED` (연베이지, 단색) |
| 카드 | `#FFFFFF` |
| CTA 컬러 | `#5BA892` (세이지 그린) |
| 텍스트 | `#2D3A32` (짙은 숲색) |
| 폰트 | Pretendard Variable (한국어) / Noto Sans JP (일본어) |
| 카드 radius | 18px |
| 버튼 radius | 999px (pill) |
| 카드 간격 | 24px |
| 섹션 간격 | 48px (넉넉하게) |
| 최대 폭 | 430px (iPhone 15 Pro Max) |
| 그림자 | 거의 없음 |

> 상세: `docs/DESIGN_TOKENS.md` + `src/styles/design-tokens.css`

---

## 6️⃣ 🚫 하지 말아야 할 것 (가장 중요!)

### 코드/구조
1. ❌ **React/Vue/Tailwind 도입 금지** → Vanilla JS + 커스텀 CSS
2. ❌ **로그인/회원가입 만들지 말 것** → 닉네임만 (localStorage)
3. ❌ **서버사이드 렌더링 X** → 완전 정적
4. ❌ **data/*.json 직접 수정 금지** → Actions가 덮어씀
5. ❌ **API 키를 코드에 직접 쓰지 말 것** → `.env` + GitHub Secrets만

### 디자인
6. ❌ **초원 앱 스타일(브라운)로 되돌리지 말 것** → 세이지 그린 확정
7. ❌ **종이 질감 배경 X** → 단색 `#F7F4ED`
8. ❌ **과한 그림자·애니메이션 X** → 미니멀
9. ❌ **이모지 폭격 금지** → 포인트용으로만

### 내용
10. ❌ **설교조/훈계체 금지** → 공감하며 함께 생각하는 톤
11. ❌ **영어 UI 금지** → 한국어 전용 (일본어 버전은 별도 i18n)

---

## 7️⃣ 🗂️ 폴더 구조

```
jumanna-qt-full/
├── BRIEFING.md          ← 이 파일 (AI 첫 인사용)
├── HANDOFF.md           ← 상세 인수인계
├── CONTEXT.md           ← 현재 상태 스냅샷
├── NEXT_STEPS.md        ← 할 일 체크리스트
├── PROMPT_TEMPLATES.md  ← 작업별 요청 템플릿
├── JAPANESE_LOCALIZATION_PLAN.md  ← 일본어 현지화 계획
│
├── docs/                ← 설계 문서 (읽기용)
│   ├── README.md
│   ├── USER_FLOW.md     ← 4단계 화면 상세
│   ├── DESIGN_TOKENS.md ← 디자인 시스템
│   ├── AI_PROMPT.md     ← GPT 프롬프트
│   ├── DATA_SCHEMA.md   ← JSON 구조
│   ├── SCRAPER.md       ← 크롤링 로직
│   └── ROADMAP.md
│
├── scripts/             ← Python 백엔드
│   ├── fetch_qt.py
│   ├── generate_ai.py
│   └── requirements.txt
│
├── data/                ← 자동 생성 JSON (손대지 말 것)
│   ├── qt/YYYY-MM-DD.json
│   └── ai/YYYY-MM-DD.json
│
└── src/                 ← 프론트엔드
    ├── index.html
    ├── step-1-scripture.html
    ├── step-2-meditation.html (예정)
    ├── step-3-prayer.html (예정)
    ├── step-4-record.html (예정)
    ├── step-5-done.html (예정)
    ├── archive.html (예정)
    ├── preview.html
    ├── scripts/
    │   ├── storage.js
    │   └── common.js
    └── styles/
        ├── design-tokens.css
        └── common.css
```

---

## 8️⃣ 사용자 프로필 (AI가 알아야 할 것)

- **비전공 바이브 코더** — 이론보다 실용, 복잡한 설명보다 **쉬운 비유** 선호
- **한국어로 소통** — 영어 답변 금지
- **정중한 말투 선호** — 너무 캐주얼하지 않게
- **iPhone/iOS 환경 중심** — 안드로이드 고려 후순위
- **코드 수정 전** → 원인 분석 & 수정 방향을 **표(table) 형태**로 먼저 제시
- **파일 단위로 명확히 구분**해서 제공 (한 번에 여러 파일 섞지 않기)
- **불필요한 설명 반복 금지** — 핵심만 간결하게

---

## 9️⃣ 📬 AI에게 드리는 첫 지시 (이 브리핑 다음에 붙일 문장 예시)

```
위 BRIEFING.md를 읽었으면 "이해 완료"라고만 답하고,
내 다음 질문을 기다려줘.

이후 내가 구체적인 작업을 요청하면:
1. 수정 전에 원인/방향을 표로 먼저 설명
2. 수정안은 파일 단위로 구분해서 제시
3. 디자인 토큰과 금지사항을 반드시 지킬 것
```

---

## 🔗 더 깊이 파고들 때 참고할 문서

| 상황 | 읽을 문서 |
|---|---|
| 전체 그림 파악 | `HANDOFF.md` + `CONTEXT.md` |
| 화면 설계 상세 | `docs/USER_FLOW.md` |
| 색상·폰트·여백 | `docs/DESIGN_TOKENS.md` |
| 데이터 구조 | `docs/DATA_SCHEMA.md` |
| GPT 프롬프트 | `docs/AI_PROMPT.md` |
| 크롤링 로직 | `docs/SCRAPER.md` |
| 일본어 현지화 | `JAPANESE_LOCALIZATION_PLAN.md` |
| 남은 할 일 | `NEXT_STEPS.md` |
| 작업별 요청 방법 | `PROMPT_TEMPLATES.md` |

---

*작성일: 2026-04-24 · Jumanna AI QT 프로젝트*
