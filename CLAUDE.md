# 주만나 AI 큐티 — Claude 작업 지침

> Claude Code가 이 프로젝트에서 작업할 때 항상 참고하는 단일 컨텍스트 파일.
> 이전: `CLAUDE_GUIDELINE.md` + `CLAUDE_HANDOVER.md` 2개 → 본 파일로 통합 (2026-05-10)

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

| 영역 | 기술 |
|---|---|
| 프론트엔드 | Vanilla JS + CSS3 (프레임워크 없음) |
| 스타일 | 커스텀 CSS (`design-tokens.css`), Tailwind 미사용 |
| 폰트 | Pretendard Variable / Noto Serif KR (CDN) |
| 저장소 | localStorage (서버 DB·로그인 없음) |
| 크롤링 | Python 3.9+ (BeautifulSoup, requests) |
| AI | OpenAI GPT-4o-mini |
| 배포 | Vercel |
| 자동화 | GitHub Actions (매일 05:00 KST) |

---

## 3. 폴더 구조

```
7.주만나 큐티/
├── docs/               설계 문서 (활성)
│   └── _archive/       구 Phase 1 문서 보관
├── scripts/            Python 백엔드 (fetch_qt.py, generate_ai.py)
├── prompts/            AI 프롬프트 정의
├── data/               자동 생성 JSON (직접 수정 금지)
├── src/                프론트엔드
│   ├── index.html
│   ├── qt/             step-1~5 화면
│   ├── styles/         design-tokens.css, common.css
│   ├── scripts/        common.js, storage.js, qr.js, supabase-sync.js
│   └── images/
├── workers/            Cloudflare Worker
├── .github/workflows/  daily_qt.yml, daily_qt_backup.yml
└── vercel.json
```

---

## 4. 핵심 규칙 (반드시 지킬 것)

### 코드
- React / Vue / Tailwind 도입 **금지** — Vanilla JS + 커스텀 CSS만
- 새 화면은 `step-1-scripture.html` 패턴을 그대로 따름
- API 키는 코드에 절대 쓰지 말 것 — `.env` 파일 전용
- `data/*.json` 직접 수정 금지 (자동화가 덮어씀)

### 디자인 (iOS/Apple HIG 기반)
- 주요 색상: `#5BA892` (세이지 그린)
- 배경: `#F7F4ED` (연베이지) / 카드: `#FFFFFF`
- 텍스트: `#2D3A32` (짙은 숲색)
- 버튼: `border-radius: 999px` (pill)
- 카드: `border-radius: 18px`, 그림자 최소화
- 최대 폭: `430px` (iPhone 15 Pro Max)
- 간격 기준: `24px` (카드), `48px` (섹션)
- vibrancy / 다층 그림자 / spring 이징 활용

### 콘텐츠 / UX
- UI는 한국어 전용
- AI 묵상 말투: 따뜻하고 공감하는 톤 (설교조·훈계체 금지)
- iPhone 환경 우선 (안드로이드 후순위)

---

## 5. 데이터 구조

### 서버 JSON (`data/qt/*.json`)
```json
{
  "date": "2026-04-22",
  "title": "회복으로 나아가라",
  "scripture_ref": "룻기 1:15-22",
  "verses": [{ "number": 15, "text": "..." }],
  "oryun_questions": ["질문1", "질문2"]
}
```

### AI JSON (`data/ai/*.json`)
```json
{
  "core_summary": ["문장1", ...5개],
  "characters": [{ "name": "나오미", "description": "..." }],
  "book_context": "룻기는 사사시대...",
  "verse_commentary": "구절 해설...",
  "application": [{ "statement": "...", "detail": "..." }],
  "prayer": ["주님,", "...", "예수님의 이름으로 기도합니다. 아멘."]
}
```

### localStorage 키
- `user.name` (기본 "어린양")
- `streak.current` / `.totalCompleted` / `.lastDate`
- `records.{date}.completed` / `.prayed` / `.emotions` / `.memo` / `.underlines`
- `settings.background` / `.fontSize` / `.fontStyle`

---

## 6. 절대 금지사항

- API 키 코드 직접 작성 / `.env` Git 커밋
- `data/*.json` 직접 수정
- React / Vue / Tailwind 도입
- 로그인·계정 시스템 추가
- 브라운 계열 색상, 과한 그림자/애니메이션, 종이 질감 배경
- 영어 UI, 설교조·훈계체 말투

---

## 7. 로컬 실행

```powershell
# 프론트엔드
python -m http.server 8000
# → http://localhost:8000/src/index.html

# iPhone 실기 테스트 (같은 Wi-Fi)
python -m http.server 8000 --bind 0.0.0.0

# Python 의존성
pip install -r scripts/requirements.txt

# AI Mock 모드
python scripts/generate_ai.py --mock

# 실제 실행 (.env 설정 후)
python scripts/fetch_qt.py
python scripts/generate_ai.py
```

---

## 8. 커뮤니케이션 방식

- 한국어 정중한 말투 (캐주얼 톤 지양)
- 코드 수정 전 원인 분석 + 수정 방향을 **표 형태**로 먼저 제시
- 수정안은 파일 단위로 구분
- git push는 사용자 명시 요청 전까지 보류 — commit만 진행
- PowerShell/git 명령은 직접 실행 (복붙 안내 금지)

---

## 9. 참고 문서 맵 (활성)

| 필요한 정보 | 파일 |
|---|---|
| 데이터 구조 | `docs/DATA_SCHEMA.md` |
| Phase 2 작업 인계 | `docs/HANDOFF_PHASE2.md` |
| Phase 2 계획 | `docs/PHASE2.md` |
| 일본어 로컬라이제이션 | `docs/JAPANESE_LOCALIZATION_PLAN.md` |
| 캘린더 UI | `docs/UI_CALENDAR.md` |
| UI 인덱스 | `docs/UI_INDEX.md` |
| UI 원칙 | `docs/UI_PRINCIPLES.md` |
| QR 모달 UI | `docs/UI_QR_MODAL.md` |

> Phase 1 문서(USER_FLOW, DESIGN_TOKENS, AI_PROMPT 등)는 `docs/_archive/` 참고
