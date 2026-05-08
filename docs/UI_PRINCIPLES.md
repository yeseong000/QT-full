# UI_PRINCIPLES — 전역 디자인 원칙

> 주만나 AI 큐티의 모든 화면이 공유하는 원칙. 새 화면 작업 시 항상 먼저 참조.

---

## 1. 핵심 원칙

| 원칙 | 의미 |
|---|---|
| 가벼움 | 인지 부담 최소화. 한 화면에 정보 블록 3개 이내. |
| 시간대 동기화 | 진입 시각에 따라 배경/인사말 자동 분기. |
| 누적 강조 | 연속성(N일 연속) 비강조, 누적(N회 완료) 강조. 큐티는 시험이 아님. |
| 전파 마찰 0 | QR 1탭으로 공유 가능. URL 복붙 불필요. |
| Vanilla 유지 | React/Vue/Tailwind 도입 금지. 외부 라이브러리 최소. |

---

## 2. 시간대 매핑

`getTimeSlot(hour)` 함수가 진입 시각으로 5개 슬롯 중 하나 반환.
CSS는 `[data-time-slot="..."]` 속성으로 분기.

| 슬롯 | 시간 | 인사말 | 톤 |
|---|---|---|---|
| `dawn` | 04~07 | 거룩한 새벽이네요 | 어두운 보라/베이지 |
| `morning` | 07~12 | 은혜로운 아침이에요 | 따뜻한 아이보리 |
| `afternoon` | 12~17 | 평안한 오후예요 | 청록/베이지 |
| `evening` | 17~22 | 온유한 저녁이네요 | 오렌지/저무는 햇빛 |
| `night` | 22~04 | 고요한 밤입니다 | 진한 네이비 |

**다크 톤 슬롯**: `dawn`, `evening`, `night` — 텍스트/아이콘 흰색 처리

```js
function getTimeSlot(hour) {
  if (hour >= 4  && hour < 7)  return 'dawn';
  if (hour >= 7  && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 22) return 'evening';
  return 'night';
}
```

---

## 3. 변경 금지 영역

다음 영역은 어떤 작업에서도 건드리지 않는다.

- `scripts/storage.js` — 데이터 스키마 보존
- `scripts/common.js` — 헬퍼 (theme/font 등)
- 5단계 묵상 화면 (`step-1-scripture` ~ `step-5-done`)
- 설정 모달의 닉네임 / 폰트 / 해시 복원 영역
- `styles/design-tokens.css`, `styles/common.css`

---

## 4. 환경별 차이

| 환경 | 동작 |
|---|---|
| 실제 배포 (Vercel) | 모든 기능 정상 |
| 로컬 정적 서버 (`python3 -m http.server`) | 배포와 동일 |
| HTML 미리보기 도구 (Claude/VSCode Preview) | 외부 스크립트 미로드 → 알약은 날짜만, 모달 펼쳐 보임 (정상 아님, 미리보기 한계) |

**테스트 권장**: `cd /path/to/QT-full && python3 -m http.server 8000` → `http://localhost:8000`
