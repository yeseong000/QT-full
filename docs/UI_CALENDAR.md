# UI_CALENDAR — 캘린더 화면 명세

> 적용 파일: `history/calendar.html`
> 전역 원칙은 `UI_PRINCIPLES.md` 참조.
> 인덱스 화면에서 좌측 상단 알약 탭 시 진입.

---

## 1. 핵심 변경 (Phase 2)

| 변경 전 | 변경 후 |
|---|---|
| `archive.html` 별도 페이지 | **흡수 — 폐기** (redirect만 남김) |
| 인라인 미리보기 = 요약만 + "전체 기록 보기" 링크 | **모든 디테일 인라인** (5개 섹션) |
| 단색 배경 | **시간대별 PNG 블러 배경** (글래스모피즘) |
| 🌱 / 🔥 이모지 | **자체 SVG 아이콘** (4단계 성장 + 잎 한 장) |
| 완료 셀 = 세이지 채움 | **완료 셀 = 점만**, 선택 시 다크 채움 |
| streak 브리지 (연결선) | 제거 — 점 하나로 충분 |

---

## 2. 레이아웃

```
┌──────────────────────────────────────────────┐
│ ←  묵상 달력                                  │  ← 헤더
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 총 묵상 횟수    │   연속                  │ │  ← 스트릭 히어로
│ │ 🌿 12회        │   🍃 3일                │ │     (글래스 카드)
│ └──────────────────────────────────────────┘ │
│                                              │
│      ‹     2026년 5월     ›                  │  ← 월 네비
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 일 월 화 수 목 금 토                       │ │
│ │              1 .. 2                       │ │  ← 달력 (글래스)
│ │  3   4 .. 5  6 .. 7   8                   │ │     . = 완료 점
│ │ 10  11 12  13 14 15 16                    │ │
│ │ ...                                       │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 🌿 점이 있는 날을 누르면…                   │ │  ← 안내 (미선택 시)
│ └──────────────────────────────────────────┘ │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 5월 6일 (수) · 완료                        │ │  ← 디테일 카드
│ │ 언약궤를 빼앗기다                           │ │     (셀 탭 시 표시,
│ │ 사무엘상 4:1-11                            │ │      안내와 교체)
│ │                                            │ │
│ │ [핵심 요약] · · ·                          │ │
│ │ [오늘의 마음] · · ·                        │ │
│ │ [밑줄 친 구절] · · ·                       │ │
│ │ [느낀 점] · · ·                            │ │
│ │ [오늘의 질문] · · ·                        │ │
│ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## 3. 시간대 배경 (글래스모피즘)

`#appContainer`에 `data-time-slot` 속성이 JS로 설정됨 (`UI_PRINCIPLES.md`의 매핑 그대로).

**구조 (3 layer)**
```html
<div class="app-container" id="appContainer">
  <div class="bg-blur"></div>       <!-- z:-2, PNG + blur(50px) saturate(0.85) -->
  <div class="bg-overlay"></div>    <!-- z:-1, 시간대별 색상 -->
  <main>...</main>                  <!-- z: auto -->
</div>
```

**오버레이 농도**
| 슬롯 | 색상 |
|---|---|
| dawn | `rgba(255,255,255,0.45)` |
| morning | `rgba(255,255,255,0.50)` |
| afternoon | `rgba(255,255,255,0.45)` |
| evening | `rgba(255,255,255,0.45)` |
| night | `rgba(0,0,0,0.40)` |

**다크 모드 (night만)**
- 텍스트/아이콘 흰색
- 글래스 카드: `rgba(255,255,255,0.12)` + 흰 보더 0.5px

---

## 4. 글래스 카드 베이스 (`.glass-card`)

모든 카드가 공유하는 베이스. 라이트/다크 톤 자동 분기.

```css
.glass-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-radius: var(--radius-lg);
}
.app-container[data-time-slot="night"] .glass-card {
  background: rgba(255, 255, 255, 0.12);
  border: 0.5px solid rgba(255, 255, 255, 0.15);
}
```

**적용 카드**: `.streak-hero`, `.calendar`, `.calendar-hint`, `.preview-card`

---

## 5. 스트릭 히어로

**구조**: 좌(2/3) — 총 묵상 / 우(1/3) — 연속. 가운데 0.5px 디바이더.

### 총 묵상 횟수 — 4단계 성장 SVG

| 단계 | 회수 | 명칭 | 모티프 |
|---|---|---|---|
| 0 | 0~6 | 씨앗 | 떡잎 2장 |
| 1 | 7~13 | 새싹 | 잎 1쌍 |
| 2 | 14~20 | 성장기 | 잎 2쌍 |
| 3 | 21~27 | 성장기+꽃봉오리 | 잎 2쌍 + 분홍 봉오리 |
| 4 | 28+ | 개화 | 잎 3쌍 + 활짝 핀 꽃 |

**28회 이후는 그대로 유지** (사이클 리셋 X).

JS 함수:
- `getGrowthStage(total)` — 0~4 반환
- `getGrowthSVG(stage)` — SVG 문자열 반환

### 연속일 — 잎 한 장

JS 함수: `getLeafSVG()` — `#5BA892` 단색 + 흰 잎맥.

---

## 6. 달력 셀 상태

| 상태 | 시각 |
|---|---|
| 빈 날 (과거/미래) | 숫자만 |
| 일요일 | 빨간 숫자 (`#C27C65`) |
| 미래 | 회색 텍스트 (`var(--text-placeholder)`) |
| 완료한 날 | 숫자 + 세이지 점(`.calendar-cell__dot`) |
| **오늘** | 세이지 보더 1.5px |
| **선택된 날** | 다크 채움 `#2D3A32` + 흰 텍스트 (+ 흰 점, 완료 시) |
| **오늘 ∩ 선택** | **다크 채움 우선** (선택 액션 피드백 우선) |

**셀 마크업**
```html
<button class="calendar-cell ..." data-date="2026-05-06">
  <span>6</span>
  <span class="calendar-cell__dot"></span>  <!-- 완료 시만 -->
</button>
```

---

## 7. 디테일 카드 (`.preview-card`) — archive 흡수

셀 탭 시 노출. 5개 섹션을 조건부 표시.

| 섹션 | 데이터 소스 | 표시 조건 |
|---|---|---|
| 핵심 요약 | `qt.core_summary` (3개 슬라이스) | 본문 데이터 있을 시 |
| 오늘의 마음 | `record.emotions` → `EMOTION_MAP` | 감정 칩 있을 시 |
| 밑줄 친 구절 | `record.underlines` | 1개 이상 |
| 느낀 점 | `record.reflection` (또는 옛 `memo`) | 텍스트 있을 시 |
| 오늘의 질문 | `record.questionAnswers` + `qt.oryun_questions` | Q&A 있을 시 |

**섹션 라벨 스타일**
- `.preview-card__section-label` — 11px, 600, `#5BA892`, `letter-spacing: 0.05em`
- 다크 모드: `#8FD4BA`

**밑줄 구절 스타일**
- 노란 배경 `rgba(245, 185, 66, 0.18)` + 좌측 `#F5B942` 3px 보더
- 우측에 `절` 표기 (작고 회색)

**상태 전환**
- 미선택 진입: 안내 카드(`.calendar-hint`) 표시 / 디테일 숨김
- 셀 탭(완료 또는 본문 있음): 안내 숨김 / 디테일 표시
- 본문도 기록도 없는 셀 탭: 디테일 숨기고 안내 다시 표시

---

## 8. 핵심 JS 함수

| 함수 | 역할 |
|---|---|
| `getTimeSlot(hour)` | 슬롯 반환 (UI_PRINCIPLES와 동일) |
| `getGrowthStage(total)` | 성장 단계 0~4 |
| `getGrowthSVG(stage)` | 성장 SVG 문자열 |
| `getLeafSVG()` | 잎 SVG 문자열 |
| `renderStreak()` | 숫자 + 아이콘 갱신 (Storage 가드 포함) |
| `collectCompletedDates()` | localStorage에서 완료일 Set 수집 |
| `renderMonth()` | 그리드 렌더 (셀 상태 분기) |
| `selectDate(date, cellEl)` | 셀 선택 + 디테일 카드 5개 섹션 렌더 |
| `clearSelection()` | 디테일 숨김 + 안내 표시 |
| `renderSummary/Emotions/Underlines/Reflection/Questions(...)` | 각 섹션 렌더 |
| `hideAllSections()` | 디테일 5개 섹션 일괄 숨김 |

**방어적 코딩**: `renderStreak`, `collectCompletedDates` 모두 `try/catch` + `Storage` 존재 가드.

---

## 9. 인터랙션 매트릭스

| 트리거 | 결과 |
|---|---|
| ← 뒤로 버튼 | `index.html` 이동 |
| ‹/› 월 네비 | 이전/다음 달 (현재 달 이후로는 이동 불가) |
| 빈 날 (과거) 탭 | 본문 데이터 있으면 디테일 + 시작 버튼, 없으면 무시 |
| 완료한 날 탭 | 디테일 카드(5개 섹션 풀) 표시 |
| 미래 셀 탭 | 비활성 (`<div>` 렌더, 클릭 X) |
| `묵상 시작하기` 탭 | `qtDate` 세션 저장 + `step-1-scripture.html` |

---

## 10. archive.html 처리

- 파일은 **유지**하되, `<meta refresh>` + JS redirect로 **즉시 `calendar.html`로 이동**
- 외부 즐겨찾기/북마크 보호 목적
- 향후 안전하게 삭제 가능 (Phase 3+)

---

## 11. 변경 금지 (Phase 2 외)

- `scripts/storage.js`, `scripts/common.js` — 데이터 스키마 보존
- 5단계 묵상 화면 — 변경 X
- `styles/design-tokens.css` — 변경 X
- 인덱스 화면 (`index.html`) — Phase 2 범위 외

---

## 12. 알려진 제약

| 항목 | 비고 |
|---|---|
| `backdrop-filter` 호환성 | iOS Safari 9+, Chrome 76+. PWA 타겟에서 문제 없음. |
| `filter: blur(50px)` 성능 | 정적 배경이라 부담 적음. 애니메이션만 안 걸면 OK. |
| HTML 미리보기 환경 | `Storage`, PNG 경로 미로드 가능 — 정상 동작 아님. 로컬 서버로 테스트 권장 |

---

## 13. 향후 개선 후보

- 캘린더 안에서 월 슬라이드 제스처 (좌/우 스와이프)
- 디테일 카드 → 본문 5단계 묵상 진입 시 데이터 prefill
- 한 해 통계 뷰 (12월 셀 그리드)
