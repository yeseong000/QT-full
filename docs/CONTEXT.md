# 📸 CONTEXT.md - 현재 상태 스냅샷

**스냅샷 시각**: 2026-04-22
**프로젝트**: 주만나 AI 큐티 (Jumanna AI QT)
**상태**: 개발 진행 중 (전체 약 45% 완료)

---

## 🎯 프로젝트 한 줄 요약

오륜교회 주만나 QT 본문을 매일 자동 스크래핑 → GPT-4o-mini로 묵상 콘텐츠 생성 → iPhone 최적화 모바일 웹에서 4단계 가이드 묵상 제공

---

## 📦 현재 구현된 것

### ✅ 완료 (동작 확인됨)

| 영역 | 파일 | 상태 |
|---|---|---|
| 프로젝트 문서 | `docs/*.md` (7개) | ✅ |
| 크롤러 | `scripts/fetch_qt.py` | ✅ (컨테이너 403, 로컬 미검증) |
| AI 생성기 | `scripts/generate_ai.py` | ✅ (Mock 동작 확인) |
| 샘플 데이터 | `data/qt/2026-04-22.json`, `data/ai/2026-04-22.json` | ✅ |
| 디자인 시스템 | `src/styles/*.css` | ✅ |
| 홈 화면 | `src/index.html` | ✅ |
| 1단계 말씀 | `src/step-1-scripture.html` | ✅ |
| 프리뷰 갤러리 | `src/preview.html` | ✅ |
| iPhone 최적화 | (CSS 전반) | ✅ (실제 iPhone 미검증) |

### 🔜 미구현

- 2단계 묵상 화면
- 3단계 적용+기도 화면
- 4단계 감정+메모 화면
- 완료 축하 화면
- 아카이브 페이지
- PWA (Manifest + Service Worker)
- GitHub Actions 자동화
- Vercel 배포

---

## 🏗️ 기술 스택 확정

| 영역 | 선택 | 이유 |
|---|---|---|
| 프론트엔드 | Vanilla JS + Tailwind 스타일 CSS | 가벼움, 디자인 집중 |
| CSS 방식 | 커스텀 CSS (Tailwind 미사용) | 토큰 시스템 직접 구성 |
| 크롤링 | Python + BeautifulSoup + lxml | 표준 |
| AI | OpenAI GPT-4o-mini | 저렴 (1년 ~550원) |
| 자동화 | GitHub Actions (예정) | 무료 |
| 배포 | Vercel (예정) | 쉬움, PWA 친화 |
| 저장소 | localStorage | 개인용, 가벼움 |
| 인증 | 이름만 (기본 "어린양님") | 가볍게 |

---

## 🎨 디자인 컨셉 확정

**테마**: 🅲️ 잔디밭 오후 + 미니멀

| 요소 | 값 |
|---|---|
| 메인 배경 | `#F7F4ED` (연베이지) |
| 카드 | `#FFFFFF` |
| CTA 컬러 | `#5BA892` (세이지 그린) |
| 텍스트 | `#2D3A32` (짙은 숲색) |
| 감정칩 | `#F5B942` / `#5BA892` / `#8B9DB8` |
| 폰트 | Pretendard Variable (CDN) |
| 카드 radius | 18px |
| 버튼 radius | 999px (pill) |
| 카드 간격 | 24px (미니멀) |
| 섹션 간격 | 48px |
| 최대 폭 | 430px (iPhone 15 Pro Max) |

→ 자세한 건 `docs/DESIGN_TOKENS.md` 참고

---

## 🚶 사용자 플로우 확정

```
🏠 홈 (인사말 + 날짜 + 연속일 + 오늘의 말씀)
   ↓
1️⃣ 말씀 (성경 본문만, 깔끔)
   ↓
2️⃣ 묵상 (AI 해설: 요약+인물+맥락+구절해설) ← 상단 말씀 토글
   ↓
3️⃣ 적용 + 기도 (실천 문장 + 기도문 + 기도했어요)
   ↓
4️⃣ 감정 + 메모 (감정 칩 + 자유 메모)
   ↓
✨ 완료 (연속일 축하 + 오늘의 내 밑줄)
```

→ 자세한 건 `docs/USER_FLOW.md` 참고

---

## 🤖 AI 콘텐츠 구조 확정

```json
{
  "core_summary": ["문장1", "문장2", "문장3", "문장4", "문장5"],
  "characters": [
    { "name": "이름", "description": "2-3문장" }
  ],
  "book_context": "책 전체 맥락 3-4문장",
  "verse_commentary": "구절 해설 3-5문장",
  "application": [
    { "statement": "나는 오늘, ~하겠습니다.", "detail": "보조 설명" }
  ],
  "prayer": ["주님,", "문장1", "", "문장2", "..."]
}
```

→ 자세한 건 `docs/AI_PROMPT.md` 참고

---

## 💾 데이터 구조 확정

**서버측 (GitHub 리포 안 JSON)**:
- `/data/qt/YYYY-MM-DD.json` - 원본 성경 본문
- `/data/ai/YYYY-MM-DD.json` - GPT 묵상 결과

**클라이언트측 (localStorage)**:
- `user.name` (기본 "어린양님")
- `streak.current`, `streak.totalCompleted`, `streak.lastDate`
- `records.{date}.*` (completed, prayed, emotions, memo, underlines)
- `settings.*` (theme, fontSize, background)

→ 자세한 건 `docs/DATA_SCHEMA.md` 참고

---

## ⚠️ 알려진 이슈

| 이슈 | 상태 | 해결 방안 |
|---|---|---|
| Claude 컨테이너에서 오륜교회 403 | 환경 이슈 | 로컬/GitHub Actions에서는 정상 예상 |
| `fetch_qt.py` 로컬 미검증 | 미확인 | 사용자가 로컬에서 한 번 실행 필요 |
| OpenAI API 미검증 | 미확인 | `.env` 설정 후 로컬 실행 필요 |
| iPhone 실기 테스트 미완료 | 미확인 | 같은 WiFi로 접속 후 확인 필요 |
| 밑줄 긋기 저장 미구현 | 기능 미완성 | Phase 6 확장 기능 |

---

## 🔑 중요한 결정 히스토리

초기 컨셉에서 현재까지의 주요 변경사항:

| 영역 | 초안 | 최종 결정 |
|---|---|---|
| 디자인 레퍼런스 | 토스(Toss) + 초원 | **잔디밭 오후 미니멀** (세이지 그린) |
| 묵상 플로우 | 단순 페이지 | **4단계 가이드형** |
| 사용자 이름 | "친구님" | **"어린양님"** (기독교 상징) |
| 기본 배경 | 종이 질감 | **단색** (미니멀) |
| AI 콘텐츠 깊이 | 짧은 요약 | **요약+인물+맥락+해설** (깊이 추가) |
| 모바일 타겟 | 범용 | **iPhone 14/15 Pro 최적화** |

→ 초기 버전은 `docs/_archive/구사양_메모_초기컨셉.md`에 보관됨

---

## 🎯 다음 작업 최우선 (지금 바로 할 것)

1. **로컬 환경 검증** (10분)
   - [ ] `python3 -m http.server 8000` 실행
   - [ ] http://localhost:8000/src/index.html 접속 → 동작 확인
   - [ ] iPhone 실기 테스트

2. **2단계 묵상 화면 구현** (30분~1시간)
   - 참고 파일: `docs/USER_FLOW.md`, `src/step-1-scripture.html`
   - 데이터: `data/ai/2026-04-22.json`

→ 자세한 작업 리스트는 `NEXT_STEPS.md`

---

## 🗂️ 폴더 구조 (현재)

```
jumanna-qt/
├── .env.example         ← API 키 템플릿
├── .gitignore
├── NEXT_STEPS.md        ← 앞으로 할 일
├── CONTEXT.md           ← 이 파일
├── HANDOFF.md           ← AI 인수인계
│
├── data/
│   ├── qt/2026-04-22.json
│   └── ai/2026-04-22.json
│
├── docs/                ← 프로젝트 설계 문서
│   ├── README.md
│   ├── UI_GUIDE.md
│   ├── USER_FLOW.md
│   ├── AI_PROMPT.md
│   ├── SCRAPER.md
│   ├── DATA_SCHEMA.md
│   ├── DESIGN_TOKENS.md
│   ├── ROADMAP.md
│   └── _archive/
│
├── scripts/             ← Python 백엔드
│   ├── README.md
│   ├── requirements.txt
│   ├── fetch_qt.py
│   └── generate_ai.py
│
└── src/                 ← 프론트엔드
    ├── README.md
    ├── index.html
    ├── step-1-scripture.html
    ├── preview.html
    ├── scripts/
    │   ├── storage.js
    │   └── common.js
    └── styles/
        ├── design-tokens.css
        └── common.css
```
