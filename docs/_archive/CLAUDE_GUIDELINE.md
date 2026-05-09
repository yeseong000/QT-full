# 주만나 AI 큐티 — Claude 프로젝트 지침

> Claude 프로젝트 "지침(System Prompt)" 영역에 붙여넣는 파일입니다.

---

## 프로젝트 개요

오륜교회 주만나 QT를 매일 자동으로 가져와 GPT가 묵상 가이드를 생성하고,  
iPhone에서 3~5분 안에 편안하게 읽을 수 있는 **개인용 성경 묵상 PWA**입니다.

- 기술: Vanilla JS + CSS3 (프레임워크 없음) / Python 크롤러 / OpenAI GPT-4o-mini / Vercel / GitHub Actions
- 디자인: 세이지 그린 (`#5BA892`) + 연베이지 배경 (`#F7F4ED`), 미니멀, iPhone 최적화
- 저장: localStorage (서버 DB 없음, 로그인 없음)

---

## 현재 진행 상황 (2026-04-29 기준, 약 45% 완료)

**완료된 것**
- Python 크롤러 (fetch_qt.py), AI 생성기 (generate_ai.py)
- 샘플 데이터 8일분 (data/qt/, data/ai/)
- 디자인 시스템 CSS (design-tokens.css, common.css)
- 홈 화면 (index.html) — 스트릭, 오늘의 말씀 카드, 설정 모달
- 1단계 말씀 화면 (step-1-scripture.html) — 하이라이트 기능
- localStorage 헬퍼 (storage.js), 공통 유틸 (common.js)
- GitHub Actions 자동화, vercel.json

**남은 것 (우선순위 순)**
1. 2단계: 묵상 화면 (step-2-meditation.html) — AI 콘텐츠 렌더링
2. 3단계: 적용+기도 (step-3-prayer.html) — 기도문 토글
3. 4단계: 감정+메모 (step-4-record.html) — 칩 선택, 자동저장
4. 5단계: 완료 축하 (step-5-done.html) — 스트릭, 밑줄 요약
5. 아카이브 화면, Vercel 배포, PWA Manifest

---

## 핵심 규칙

**코드**
- React / Vue / Tailwind 도입 금지 — Vanilla JS + 커스텀 CSS만 사용
- 새 화면 작성 시 `step-1-scripture.html` 패턴을 그대로 따를 것
- API 키는 코드에 절대 쓰지 말 것 (`.env` 파일 전용)
- `data/*.json` 직접 수정 금지 (자동화가 덮어씀)

**디자인**
- 주요 색상: `#5BA892` (세이지 그린), 배경: `#F7F4ED`, 카드: `#FFFFFF`
- 버튼은 항상 `border-radius: 999px` (pill 형태)
- 카드는 `border-radius: 18px`, 그림자 최소화
- CSS 변수는 `design-tokens.css`에서 가져올 것

**콘텐츠/UX**
- UI는 한국어 전용
- AI 묵상 말투: 따뜻하고 공감하는 톤 (설교조·훈계체 금지)
- iPhone 환경 우선 (안드로이드는 후순위)

---

## 커뮤니케이션 방식

- 한국어로 답변
- 코드 수정 전 원인 분석 + 수정 방향을 **표 형태**로 먼저 제시
- 수정안은 파일 단위로 구분해서 제시
- 핵심만 간결하게 (불필요한 반복 설명 생략)

---

## 참고 파일 (CLAUDE_HANDOVER.md에 상세 내용)

- 화면 설계: `docs/USER_FLOW.md`
- 색상/폰트: `docs/DESIGN_TOKENS.md`
- AI 프롬프트: `docs/AI_PROMPT.md`
- 데이터 구조: `docs/DATA_SCHEMA.md`
- 남은 할 일: `NEXT_STEPS.md`
