# 🎨 UI 가이드 - 초원 스타일 디자인 시스템

초원 앱(국민 성경 앱)의 감성을 참고한 모바일 웹 디자인 가이드입니다.  
**"종이 위에 손글씨로 써 내려가는 느낌"**이 핵심입니다.

---

## 🎨 컬러 팔레트

### 기본 컬러 (라이트 모드)

| 역할 | Hex | 용도 |
|---|---|---|
| `--bg-primary` | `#F5F1EA` | 메인 배경 (크림) |
| `--bg-card` | `#FFFFFF` | 카드 배경 (순백) |
| `--bg-muted` | `#EFE9DF` | 부가 영역 (옅은 베이지) |
| `--accent` | `#8B6F47` | 주요 포인트 (브라운) |
| `--accent-soft` | `#D9C9AE` | 부드러운 포인트 (연베이지) |
| `--text-primary` | `#2A2420` | 본문 텍스트 (짙은 브라운) |
| `--text-secondary` | `#8A7B6C` | 보조 텍스트 (회갈색) |
| `--text-muted` | `#B8A896` | 플레이스홀더 |

### 감정 칩 컬러

| 감정 카테고리 | 컬러 |
|---|---|
| 🟠 평온/감사 (마음이 편안해졌어요, 감사함을 느껴요, 위로를 받았어요) | `#F4A261` |
| 🟢 깨달음/결심 (깨달음을 얻었어요, 결심이 생겼어요, 의지가 커졌어요) | `#2A9D8F` |
| 🟣 돌아봄/흔들림 (나를 돌아보게 돼요, 궁금증이 생겨요, 마음이 흔들려요) | `#9B7EBD` |

### 다크 모드 (향후 지원)

| 역할 | Hex |
|---|---|
| `--bg-primary` | `#1C1915` |
| `--bg-card` | `#2A2420` |
| `--text-primary` | `#F5F1EA` |
| `--accent` | `#D9C9AE` |

---

## 🖼️ 배경 이미지 시스템

### 파일 구조

```
/public/assets/images/backgrounds/
├── paper-cream.jpg        # 기본 (초원 스타일 종이 질감)
├── paper-warm.jpg         # 따뜻한 베이지
├── paper-cool.jpg         # 차분한 그레이
├── linen.jpg              # 린넨 질감
└── custom-*.jpg           # 사용자가 추가 가능
```

### 교체 방법 (직접 수정 시)

1. `/public/assets/images/backgrounds/` 폴더에 새 이미지 추가
2. `config/backgrounds.json`에 항목 추가:

```json
{
  "id": "my-bg",
  "name": "나의 배경",
  "file": "my-bg.jpg",
  "thumbnail": "my-bg-thumb.jpg"
}
```

3. 설정 화면에서 자동으로 표시됨

### 이미지 권장 사양

- **해상도**: 1080 × 2340 (9:19.5 비율 모바일)
- **용량**: 200KB 이하 (웹 성능 고려)
- **톤**: 부드럽고 옅은 색상, 본문 가독성을 해치지 않을 것
- **포맷**: JPG 또는 WebP

---

## ✒️ 타이포그래피

### 폰트 스택

```css
/* 본문/UI */
font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;

/* 성경 본문 (좀 더 책 같은 느낌) */
font-family: 'Noto Serif KR', 'Nanum Myeongjo', serif;

/* 숫자/영문 (연속일 카운터 등) */
font-family: 'Inter', sans-serif;
```

### 크기 스케일

| 역할 | 크기 | 굵기 | 예시 |
|---|---|---|---|
| `--text-hero` | 28px | 700 | 오늘의 말씀 제목 |
| `--text-h1` | 22px | 700 | "말씀을 깊이 새겨보세요" |
| `--text-h2` | 18px | 600 | 섹션 헤더 |
| `--text-body` | 16px | 400 | 본문 |
| `--text-scripture` | 17px | 400 | 성경 구절 (명조체) |
| `--text-small` | 14px | 400 | 날짜, 보조 정보 |
| `--text-caption` | 12px | 400 | 캡션 |

---

## 🧩 컴포넌트 스타일

### 카드 (Card)

```css
.card {
  background: var(--bg-card);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(42, 36, 32, 0.04);
  margin-bottom: 16px;
}
```

### 버튼 (Primary - "다음")

```css
.btn-primary {
  background: var(--accent);      /* 브라운 */
  color: white;
  border-radius: 999px;           /* pill shape */
  padding: 14px 32px;
  font-weight: 600;
  font-size: 16px;
}
```

### 버튼 (Secondary - "이전")

```css
.btn-secondary {
  background: var(--accent-soft); /* 연베이지 */
  color: var(--accent);
  border-radius: 999px;
  padding: 14px 24px;
}
```

### 감정 칩 (Chip)

```css
.chip {
  border: 1px solid var(--text-muted);
  border-radius: 999px;
  padding: 10px 16px;
  background: transparent;
  /* 앞에 컬러 닷 추가 */
}
.chip::before {
  content: '●';
  color: var(--chip-color);
  margin-right: 6px;
}
```

### 하단 네비게이션 바

- 하단 고정 (fixed)
- "← 이전" 버튼 (작게) + "다음 →" 버튼 (크게, 브라운)
- 마지막 단계에서는 "완료하기"로 변경

### 플로팅 액션 버튼 (FAB)

- 우하단 고정
- 밑줄 긋기 모드 토글, 책 아이콘(말씀 다시보기) 등

---

## 📐 레이아웃 원칙

1. **모바일 퍼스트**: max-width 430px 기준 디자인
2. **여백 풍부하게**: 카드 간 16px, 카드 안쪽 20px
3. **스크롤은 수직만**: 가로 스크롤 절대 금지
4. **하단 네비게이션바 공간 확보**: `padding-bottom: 100px`
5. **세이프 에어리어 대응**: `padding-bottom: env(safe-area-inset-bottom)`

---

## 🎭 애니메이션 / 모션

| 동작 | 효과 |
|---|---|
| 페이지 전환 | 부드러운 fade + slide (300ms) |
| 카드 등장 | 아래에서 위로 살짝 올라오며 fade-in (400ms) |
| 버튼 탭 | scale(0.97) 아주 살짝 눌림 |
| 체크박스 | 부드러운 tick 애니메이션 |
| 연속일 달성 | 은은한 컨페티 또는 별 반짝임 |

**원칙**: 과하지 않게. 초원 앱은 거의 움직임이 없어서 오히려 차분한 느낌.

---

## 🔍 밑줄 긋기 UX

- 텍스트를 길게 누르면 (long-press) 밑줄 모드 진입
- 드래그로 범위 선택
- 손놓으면 노란 형광펜 느낌의 밑줄 그어짐
- 탭하면 해제 또는 메모 추가
- localStorage에 `{ date, verse: "1:15", text: "...", range: [10, 30] }` 저장

---

## 📖 말씀 재확인 토글 (2단계 상단)

```
┌────────────────────────────────┐
│  📖 룻기 1:15-22        ▼       │  ← 접혀있는 상태 (작게)
└────────────────────────────────┘

탭하면 ↓

┌────────────────────────────────┐
│  📖 룻기 1:15-22        ▲       │
│                                │
│  15 나오미가 또 이르되...        │
│  16 룻이 이르되...              │
│  (전체 본문)                    │
└────────────────────────────────┘
```

---

## ✅ 디자인 체크리스트

- [ ] 모든 텍스트가 한 손 엄지로 읽힐 위치에 있는가?
- [ ] 버튼이 탭하기 쉬운 크기인가? (최소 44×44px)
- [ ] 배경 이미지가 본문 가독성을 해치지 않는가?
- [ ] 다크 모드에서도 색 대비가 충분한가?
- [ ] iOS 세이프 에어리어에 가려지는 UI가 없는가?
