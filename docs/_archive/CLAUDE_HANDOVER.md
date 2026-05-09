# 주만나 AI 큐티 — Claude 인수인계 문서

> 이 파일을 Claude 프로젝트에 업로드하면 언제든 컨텍스트를 이어갈 수 있습니다.  
> 최종 업데이트: 2026-04-29 | 진행률: 약 45%

---

## 1. 프로젝트 정체성

**이름**: 주만나 AI 큐티 (Jumanna AI QT)  
**형태**: 개인용 성경 묵상 모바일 웹앱 (PWA)  
**대상**: 개발자 본인 — 매일 아침 iPhone에서 3~5분 묵상  
**호스팅**: Vercel (정적) + GitHub Actions (자동화)

### 핵심 철학
| 키워드 | 내용 |
|---|---|
| 가벼움 | 과하지 않은 3~5분 아침 루틴 |
| 자동화 | 사용자는 아무것도 하지 않아도 매일 최신 QT 준비 |
| 분위기 | 잔디밭 오후 + 미니멀 (세이지 그린 톤) |
| 기록 | 밑줄·메모·감정이 쌓여 성장감을 느낌 |

---

## 2. 기술 스택

| 영역 | 기술 | 비고 |
|---|---|---|
| 프론트엔드 | Vanilla JS + CSS3 | 프레임워크 없음 |
| 스타일 | 커스텀 CSS (design-tokens.css) | Tailwind 미사용 |
| 폰트 | Pretendard Variable / Noto Serif KR | CDN |
| 저장소 | localStorage | 서버 DB 없음 |
| 크롤링 | Python 3.9+ (BeautifulSoup, requests) | 오륜교회 주만나 |
| AI | OpenAI GPT-4o-mini | 연 비용 ~550원 |
| 배포 | Vercel | 정적 호스팅 |
| 자동화 | GitHub Actions | 매일 05:00 KST |

---

## 3. 폴더 구조

```
jumanna-qt-full/
├── docs/               설계 문서 (읽기용)
│   ├── USER_FLOW.md    4단계 화면 상세 설계
│   ├── DESIGN_TOKENS.md 색상·폰트·여백 정의
│   ├── AI_PROMPT.md    GPT 프롬프트 + 페르소나
│   ├── DATA_SCHEMA.md  JSON 구조 + localStorage 설계
│   └── ROADMAP.md      MVP → 확장 로드맵
│
├── scripts/            Python 백엔드 자동화
│   ├── fetch_qt.py     오륜교회 QT 크롤링 (363줄)
│   ├── generate_ai.py  GPT-4o-mini 묵상 생성 (634줄)
│   └── requirements.txt
│
├── data/               자동 생성 JSON (직접 수정 금지)
│   ├── qt/             스크래핑 원본 (8일분)
│   └── ai/             AI 묵상 콘텐츠 (8일분)
│
├── src/                프론트엔드
│   ├── index.html              홈 화면 ✅ 완료
│   ├── step-1-scripture.html   1단계: 말씀 화면 ✅ 완료
│   ├── styles/
│   │   ├── design-tokens.css   CSS 변수 (색상·폰트·간격)
│   │   └── common.css          iPhone 최적화 컴포넌트
│   └── scripts/
│       ├── storage.js          localStorage 헬퍼
│       ├── common.js           공통 유틸
│       └── supabase-sync.js    클라우드 동기화 (선택)
│
├── .github/workflows/
│   ├── daily_qt.yml            메인 GitHub Actions
│   └── daily_qt_backup.yml     백업
│
└── vercel.json                 배포 캐시 설정
```

---

## 4. 사용자 플로우 (4단계)

```
홈 화면
  → 1단계: 말씀 읽기 (성경 본문 + 하이라이트) ✅
  → 2단계: 묵상 (AI 핵심 요약 5줄 + 인물 + 맥락) 🔜
  → 3단계: 적용 + 기도 (적용 3개 + 기도문 토글) 🔜
  → 4단계: 감정 + 메모 (칩 선택 + 자동저장) 🔜
  → 완료 화면 (스트릭 + 축하) 🔜
```

---

## 5. 디자인 시스템 핵심

| 항목 | 값 |
|---|---|
| 배경 | `#F7F4ED` (연베이지) |
| 카드 | `#FFFFFF` |
| 주요 색상 (CTA) | `#5BA892` (세이지 그린) |
| 텍스트 | `#2D3A32` (짙은 숲색) |
| 카드 라디우스 | `18px` |
| 버튼 라디우스 | `999px` (pill) |
| 최대 폭 | `430px` (iPhone 15 Pro Max) |
| 간격 기준 | `24px` (카드), `48px` (섹션) |

---

## 6. 데이터 구조 요약

### 서버 JSON (data/qt/*.json)
```json
{
  "date": "2026-04-22",
  "title": "회복으로 나아가라",
  "scripture_ref": "룻기 1:15-22",
  "verses": [{ "number": 15, "text": "..." }],
  "oryun_questions": ["질문1", "질문2"]
}
```

### AI JSON (data/ai/*.json)
```json
{
  "core_summary": ["문장1", "문장2", "문장3", "문장4", "문장5"],
  "characters": [{ "name": "나오미", "description": "..." }],
  "book_context": "룻기는 사사시대...",
  "verse_commentary": "구절 해설...",
  "application": [{ "statement": "나는 오늘...", "detail": "..." }],
  "prayer": ["주님,", "...", "예수님의 이름으로 기도합니다. 아멘."]
}
```

### localStorage 키
- `user.name` — 닉네임 (기본: "어린양")
- `streak.current` / `streak.totalCompleted` / `streak.lastDate`
- `records.{date}.completed` / `.prayed` / `.emotions` / `.memo` / `.underlines`
- `settings.background` / `.fontSize` / `.fontStyle`

---

## 7. 구현 진행 상황

### ✅ 완료 (45%)
- 설계 문서 전체 (docs/*)
- Python 크롤러 (fetch_qt.py)
- Python AI 생성기 (generate_ai.py)
- 샘플 데이터 8일분 (data/qt/, data/ai/)
- 디자인 시스템 CSS (design-tokens.css, common.css)
- 홈 화면 (index.html) — 스트릭, 오늘의 말씀, 설정 모달 포함
- 1단계 말씀 화면 (step-1-scripture.html) — 하이라이트 기능 포함
- JavaScript 헬퍼 (storage.js, common.js)
- vercel.json, GitHub Actions 워크플로

### 🔜 미구현 (55%)
| 우선순위 | 항목 | 파일명 |
|---|---|---|
| 🔴 높음 | 2단계: 묵상 화면 | step-2-meditation.html |
| 🔴 높음 | 3단계: 적용+기도 | step-3-prayer.html |
| 🔴 높음 | 4단계: 감정+메모 | step-4-record.html |
| 🟡 중간 | 5단계: 완료 축하 | step-5-done.html |
| 🟡 중간 | 아카이브 화면 | archive.html |
| 🟡 중간 | 크롤러 실환경 검증 | — |
| 🟡 중간 | Vercel 배포 | — |
| 🟢 낮음 | PWA Manifest | manifest.json |
| 🟢 낮음 | Service Worker | sw.js |

---

## 8. 절대 금지사항

### 코드
- API 키를 코드에 직접 작성 → `.env` 파일 전용
- `.env` 파일 Git 커밋 (이미 `.gitignore` 적용됨)
- `data/*.json` 직접 수정 → GitHub Actions가 덮어씀
- React / Vue / Tailwind 도입
- 로그인/계정 시스템 추가

### 디자인
- 브라운 계열 색상 사용 (세이지 그린 `#5BA892` 유지)
- 과한 그림자 / 애니메이션
- 종이 질감 배경 (단색 `#F7F4ED` 유지)

### 콘텐츠
- 영어 UI (한국어 전용)
- 설교조 / 훈계체 말투 (따뜻하고 공감하는 톤)

---

## 9. 로컬 실행 방법

```bash
# 프론트엔드 (프로젝트 루트에서)
python3 -m http.server 8000
# → http://localhost:8000/src/index.html

# iPhone 실기 테스트 (같은 Wi-Fi)
python3 -m http.server 8000 --bind 0.0.0.0
# → iPhone Safari: http://[PC IP]:8000/src/index.html

# Python 의존성 설치
pip install -r scripts/requirements.txt

# AI 생성 (Mock 모드, API 없이)
python scripts/generate_ai.py --mock

# 실제 실행 (.env에 OPENAI_API_KEY 입력 후)
python scripts/fetch_qt.py
python scripts/generate_ai.py
```

---

## 10. 참고 문서 맵

| 필요한 정보 | 읽을 파일 |
|---|---|
| 화면 설계 | `docs/USER_FLOW.md` |
| 색상/폰트/여백 | `docs/DESIGN_TOKENS.md` |
| AI 프롬프트 | `docs/AI_PROMPT.md` |
| 데이터 구조 | `docs/DATA_SCHEMA.md` |
| 크롤러 로직 | `docs/SCRAPER.md` |
| 로드맵 | `docs/ROADMAP.md` |
| 할 일 목록 | `NEXT_STEPS.md` |
