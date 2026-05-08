# UI_INDEX — 인덱스 화면 명세

> 적용 파일: `index.html`
> 전역 원칙은 `UI_PRINCIPLES.md` 참조.

---

## 1. 레이아웃

```
┌──────────────────────────────────────────────┐
│ [날짜·N회완료]   spacer   [QR]  [설정]       │  ← 헤더 (44px)
│                                              │
│ 온유한 저녁이네요                            │  ← 인사말
│                                              │
│            (시간대별 PNG 배경)                │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ ⏱ 약 3분 소요                             │ │
│ │ 오늘 본문 제목                             │ │  ← 오늘의 말씀 카드
│ │ 사무엘상 4:12-22                          │ │     (하단 안전 영역)
│ │ [   묵상 시작하기   ]                     │ │
│ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## 2. 헤더 (`.home-header`)

### 좌측 — 날짜 알약 (`.date-pill` / `#datePill`)

| 상태 | 표시 |
|---|---|
| 0회 완료 | `26년 5월 8일 (금)` |
| 1회 이상 | `26년 5월 8일 (금) · 12회 완료` |

**스타일 핵심**
- `min-height: 32px`, `padding: 7px 14px`, `border-radius: 999px`
- `font-size: 12.5px`, `font-weight: 500`, `white-space: nowrap`
- 라이트 톤: `bg rgba(255,255,255,0.85)` + `backdrop-filter: blur(8px)`
- 다크 톤: `bg rgba(0,0,0,0.28)` + 흰 텍스트

**서브 클래스**: `.date-pill__sep` (가운뎃점 0.5 투명) / `.date-pill__count` (N회 600 weight)

**클릭**: `history/calendar.html`로 이동.

### 우측 — 아이콘 2개

| 버튼 | ID | 동작 |
|---|---|---|
| QR 공유 | `#qrShareBtn` | QR 모달 오픈 (`UI_QR_MODAL.md` 참조) |
| 설정 | `#settingsBtn` | 설정 모달 오픈 |

공통: `.icon-btn`, 36×36px, 투명 배경. 다크 톤에서 흰색 처리.

### spacer

`.home-header__spacer { flex: 1; }` — 좌측 알약과 우측 아이콘 그룹 사이 자동 정렬.

---

## 3. 인사말 (`.greeting-section`)

| 요소 | 명세 |
|---|---|
| `.greeting-text` (`#greetingText`) | `font-size: var(--text-hero)`, `font-weight: 700`, `line-height: 1.25` |
| 다크 톤 | 흰색 + `text-shadow: 0 1px 8px rgba(0,0,0,0.18)` |

**날짜 줄 없음**. 날짜는 헤더 알약으로 통합됨.

세리프 폰트 시 오버플로 방지: 28px로 다운사이즈.

---

## 4. 오늘의 말씀 카드 (`.today-card`)

| 영역 | 내용 |
|---|---|
| 메타 | `⏱ 약 3분 소요` (`.today-meta`) |
| 제목 | `<h2 class="today-title">` |
| 구절 | `<p class="today-ref">` — `사무엘상 4:12-22` 형식 |
| CTA | `묵상 시작하기` 버튼 — 시간대별 다크 컬러 |

**시간대별 CTA 색상**
- dawn `#2D3A5C` / morning `#4A3520` / afternoon `#2D4A5C` / evening `#4A1F2E` / night `#2D3658`

**위치**: flex column으로 화면 하단 안전 영역 자동 정렬.
**상태**: 로딩 / 콘텐츠 / 에러 — JS에서 `display` 토글.

---

## 5. 인터랙션 매트릭스

| 트리거 | 결과 |
|---|---|
| 좌측 알약 탭 | `history/calendar.html` 이동 |
| QR 아이콘 탭 | QR 모달 오픈 |
| 설정 아이콘 탭 | 설정 모달 오픈 |
| `묵상 시작하기` 탭 | `step-1-scripture.html` 이동 |
| 인사말/카드 탭 | 동작 없음 |

---

## 6. 핵심 JS 함수

| 함수 | 역할 |
|---|---|
| `getTimeSlot(hour)` | 시간대 슬롯 반환 (`UI_PRINCIPLES.md` 참조) |
| `renderGreeting(slot)` | 인사말 텍스트 렌더 |
| `renderDatePill()` | 헤더 알약 렌더 (Storage 미정의 시 0회로 폴백) |
| `loadTodayQT()` | 오늘 QT 데이터 fetch + 카드 렌더 |

**방어적 코딩**: `renderDatePill`은 `typeof Storage` 가드 + `try/catch`로 보호.
