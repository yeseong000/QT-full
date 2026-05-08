# HANDOFF — VS Code 작업 인계

> Phase 1, 2 완료 산출물 적용 가이드.
> 새 작업 세션 시작 전 이 문서 한 번 훑고 시작.

---

## 1. 한눈에 보기

| 단계 | 결과 | 상태 |
|---|---|---|
| Phase 1 | 인덱스 헤더 개편 (날짜 알약 + QR + 설정) + QR 모달 | ✅ 완료 |
| Phase 2 | 캘린더 통합 (글래스 배경 + SVG 아이콘 + archive 흡수) | ✅ 완료 |
| Phase 3 | 5단 호흡 카드 GPT 프롬프트 v1 | ⏳ 다음 |

**핵심 변경 요약 (3줄)**
- 인덱스: `🌱 N일 연속` 알약 → `26년 5월 8일 (금) · N회 완료` 알약 / 책 아이콘 → QR 아이콘
- 캘린더: 시간대별 PNG 블러 배경 + 글래스 카드 / archive 디테일을 셀 탭 시 인라인으로 흡수
- archive.html → calendar.html로 redirect (외부 링크/즐겨찾기 보호)

---

## 2. 적용 매트릭스

### 코드 파일 (5개)

| 위치 | 파일 | 작업 | 비고 |
|---|---|---|---|
| 루트 | `index.html` | **덮어쓰기** | 헤더/CSS/JS 광범위 변경 |
| 루트 | `vercel.json` | **신규** (또는 기존에 병합) | archive → calendar redirect |
| `scripts/` | `qr.js` | **신규** | Vanilla JS QR 생성 (MIT, 외부 의존 0) |
| `history/` | `calendar.html` | **덮어쓰기** | 글래스 배경 + 5섹션 디테일 |
| `history/` | `archive.html` | **덮어쓰기** | redirect 페이지로 변환 |

### 명세 문서 (5개)

> 프로젝트 루트 또는 `docs/` 디렉토리 어디든. **신규 파일이므로 어디 두든 OK**.

| 파일 | 역할 |
|---|---|
| `PHASE.md` | 작업 흐름 핸드오프 (Phase 1~2 진행 상황) |
| `UI_PRINCIPLES.md` | 전역 디자인 원칙 + 시간대 매핑 (모든 화면 공유) |
| `UI_INDEX.md` | 인덱스 화면 명세 |
| `UI_QR_MODAL.md` | QR 모달 명세 |
| `UI_CALENDAR.md` | 캘린더 화면 명세 |

### 적용 순서 (안전한 순서)

1. **백업** — 현재 `index.html`, `history/calendar.html`, `history/archive.html` git commit 또는 별도 보관
2. **신규 파일 추가** (덮어쓰기 위험 없음)
   - `scripts/qr.js`
   - `vercel.json`
   - 명세 문서 5개
3. **로컬 테스트** — `python3 -m http.server 8000`으로 신규 파일만 있는 상태에서 사이트 정상인지 확인
4. **덮어쓰기**
   - `index.html`
   - `history/calendar.html`
   - `history/archive.html`
5. **검증 체크리스트 수행** (3번 섹션)
6. **Vercel 배포** — git push로 자동 배포

---

## 3. 검증 체크리스트

로컬 서버(`python3 -m http.server 8000`) 또는 Vercel 배포 후 시크릿 창에서.

### 인덱스 화면

- [ ] 좌상단 알약 표시 → `26년 5월 8일 (금) · N회 완료` 형식
- [ ] 0회 완료 사용자 → `26년 5월 8일 (금)`만 표시
- [ ] 우상단 QR 아이콘 + 설정 아이콘 (책 아이콘 없음)
- [ ] 인사말 큰 텍스트만, 아래 날짜 줄 없음
- [ ] 시간대별 인사말 동기화 (PC 시계 조정 후 새로고침)
- [ ] QR 아이콘 탭 → QR 모달 슬라이드 업, 폰 카메라로 스캔 시 사이트 이동
- [ ] QR 모달 "복사" 버튼 → 1.5초 "복사됨" 표시 → 원복
- [ ] 알약 탭 → `history/calendar.html` 이동

### 캘린더 화면

- [ ] 진입 시 시간대별 PNG 블러 배경 표시
- [ ] 모든 카드(스트릭/달력/안내/디테일) 글래스 효과
- [ ] 스트릭 히어로 SVG: 좌측 성장 단계(0~6 씨앗 / 7~13 새싹 / 14~20 성장기 / 21~27 꽃봉오리 / 28+ 개화), 우측 잎 한 장
- [ ] 셀 상태: 빈 날(숫자) / 완료(숫자+세이지 점) / 오늘(세이지 보더) / 선택(다크 채움)
- [ ] 오늘 ∩ 선택 = 다크 채움 우선
- [ ] 미선택 시 안내 카드 "🌿 점이 있는 날을 누르면…" 표시
- [ ] 완료한 날 셀 탭 → 디테일 카드(핵심 요약 / 마음 / 밑줄 / 느낀점 / Q&A) 노출
- [ ] "전체 기록 보기" 링크 없음 (archive 흡수 완료)
- [ ] 빈 셀 다시 탭 → 안내 카드 복귀
- [ ] 밤(22~04) 시간대 → 다크 모드 (흰 글래스 + 흰 텍스트)

### archive.html redirect

- [ ] `/history/archive.html` 직접 접속 → `calendar.html`로 즉시 이동
- [ ] `/archive.html` 또는 `/archive` (Vercel 환경) → `/history/calendar.html`로 redirect (vercel.json)

### 보존 영역 (변경되지 않았는지)

- [ ] 5단계 묵상 화면 (`step-1-scripture` ~ `step-5-done`) 정상
- [ ] 설정 모달의 닉네임 / 폰트 / 해시 복원 정상
- [ ] storage.js 데이터 손실 없음 (이전 묵상 기록 유지)

---

## 4. 코딩 어시스턴트 (Cursor/Copilot Chat) 컨텍스트 프롬프트

> 새 세션 시작 시 코딩 어시스턴트에 첫 메시지로 붙여넣기:

```
주만나 AI 큐티 PWA 프로젝트입니다.

## 기술 스택
- Vanilla JS + 커스텀 CSS (React/Vue/Tailwind 금지)
- Python + BeautifulSoup (크롤링)
- OpenAI GPT-4o-mini (콘텐츠 생성)
- localStorage (저장)
- Vercel + GitHub Actions (배포)

## 현재 상태
Phase 1 (인덱스 헤더 + QR 모달), Phase 2 (캘린더 통합) 완료.
다음 작업: 5단 호흡 카드 GPT 시스템 프롬프트 v1.

## 핵심 명세 (이 문서들 먼저 읽어주세요)
- UI_PRINCIPLES.md — 시간대 매핑, 디자인 원칙
- UI_INDEX.md — 인덱스 화면
- UI_QR_MODAL.md — QR 모달
- UI_CALENDAR.md — 캘린더 화면
- PHASE.md — 작업 흐름

## 작업 규칙
- 코드 수정 전 반드시 원인+방향을 표(table)로 먼저 제시 → 동의 받기 → 코딩
- 파일 단위로 명확히 구분
- 변경 사항 요약 표 함께 제공
- 한국어로 답변

## 보존 영역 (절대 변경 금지)
- scripts/storage.js (데이터 스키마)
- scripts/common.js (헬퍼)
- 5단계 묵상 화면 (step-1-scripture ~ step-5-done)
- 설정 모달 내부 (닉네임/폰트/해시)
- styles/design-tokens.css, styles/common.css
```

---

## 5. 다음 라운드 — Phase 3 (5단 호흡 카드 GPT 프롬프트 v1)

이 작업은 **새 Claude 대화 세션**에서 진행 권장 (UI 작업과 영역이 다름, 컨텍스트 분리).

**진행 시 첨부할 자료**
- `userMemories`에 정리된 R1~R6 6가지 작성 패턴
- 원본 예시 10개 vs 편집본 비교 데이터
- 이미 작성된 GPT 시스템 프롬프트 v1 초안 (있을 경우)
- `HANDOFF_PHASE1_5STEP_BREATH.md` (있을 경우)

**시작 프롬프트 예시**
```
주만나 AI 큐티의 5단 호흡 카드 시스템 GPT 프롬프트 v1 작업을 이어갑니다.
이전 세션에서 6가지 작성 패턴(R1~R6)이 도출됐고, 시스템 프롬프트 초안이 있습니다.
다음 단계는 fewshot JSON 예시 제작입니다.
```

---

## 6. 알려진 이슈 & 확인 사항

| 이슈 | 조치 |
|---|---|
| HTML 미리보기 도구에서 깨져 보임 | 정상. PWA 환경 + 외부 스크립트 미로드 한계. 로컬 서버나 배포로 테스트 |
| iOS Safari `backdrop-filter` | iOS 9+ 지원. 실기기 테스트 권장 |
| PNG 자산 1x → 모바일에서 흐림 | GPT-4o로 3x(1179×2556) 재생성 예정 (대장님 외부 작업) |
| Vercel 배포 후 archive 캐시 404 | 시크릿 창 또는 `?v=2` 쿼리로 강제 새로고침 |
