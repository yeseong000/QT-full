# 🎨 디자인 토큰 명세서

**테마**: 🅲️ 잔디밭 오후 (Fresh & Friendly)
**방향**: 미니멀 · 넉넉한 여백 · 정적
**무드**: 세이지 그린 · 맑고 친근 · 시간 무관 범용

> `UI_GUIDE.md`의 세부 구현 명세이며, 실제 CSS 변수(`design-tokens.css`)와 1:1 매칭됩니다.

---

## 🧭 디자인 철학

| 원칙 | 설명 |
|---|---|
| **넉넉한 여백** | 카드 간격 24px, 섹션 간격 48px (초원보다 1.5배) |
| **정적인 미니멀** | 그림자 최소화, 장식적 요소 제거 |
| **세이지 그린** | 자연스럽고 성장을 상징하는 컬러 |
| **시간 무관** | 아침/저녁 모두 편하게 쓸 수 있는 중립적 톤 |
| **친근함** | 부드러운 radius (18-24px), 완전 둥근 버튼 |

---

## 🎨 1. 컬러 팔레트

### 배경

| 토큰 | HEX | 사용처 |
|---|---|---|
| `--bg-paper` | `#F7F4ED` | 앱 전체 배경 (연베이지) |
| `--bg-card` | `#FFFFFF` | 카드 내부 |
| `--bg-soft` | `#E8F0EA` | 부드러운 영역 |
| `--bg-input` | `#FAFAF7` | 입력창 |

### 텍스트

| 토큰 | HEX | 사용처 |
|---|---|---|
| `--text-primary` | `#2D3A32` | 짙은 숲색 - 제목 |
| `--text-body` | `#3D4A42` | 본문 |
| `--text-secondary` | `#7A857E` | 보조, 날짜 |
| `--text-placeholder` | `#B0B9B4` | 플레이스홀더 |
| `--text-on-accent` | `#FFFFFF` | 세이지 버튼 위 |

### 액센트 (세이지 그린)

| 토큰 | HEX | 사용처 |
|---|---|---|
| `--accent-sage` | `#5BA892` | 메인 CTA |
| `--accent-sage-dark` | `#4A8F7C` | hover |
| `--accent-sage-soft` | `#E8F0EA` | 보조 버튼 배경 |
| `--accent-sage-text` | `#4A8F7C` | 보조 버튼 텍스트 |

### 감정 칩

| ID | 라벨 | 컬러 | 카테고리 |
|---|---|---|---|
| `peaceful` | 마음이 편안해졌어요 | `#F5B942` 🟡 | 평온 |
| `grateful` | 감사함을 느껴요 | `#F5B942` 🟡 | 평온 |
| `comforted` | 위로를 받았어요 | `#F5B942` 🟡 | 평온 |
| `insight` | 깨달음을 얻었어요 | `#5BA892` 🟢 | 깨달음 |
| `resolved` | 결심이 생겼어요 | `#5BA892` 🟢 | 깨달음 |
| `strengthened` | 의지가 커졌어요 | `#5BA892` 🟢 | 깨달음 |
| `reflective` | 나를 돌아보게 돼요 | `#8B9DB8` 🔵 | 돌아봄 |
| `curious` | 궁금증이 생겨요 | `#8B9DB8` 🔵 | 돌아봄 |
| `shaken` | 마음이 흔들려요 | `#8B9DB8` 🔵 | 돌아봄 |

---

## ✒️ 2. 타이포그래피

### 폰트

```css
--font-sans: 'Pretendard Variable', 'Pretendard', -apple-system, sans-serif;
```

CDN: `https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.css`

### 크기

| 토큰 | 크기 | 굵기 | line-height | 용도 |
|---|---|---|---|---|
| `--text-hero` | 28px | 700 | 1.35 | 페이지 대제목 |
| `--text-h1` | 22px | 700 | 1.4 | 카드 제목 |
| `--text-h2` | 18px | 700 | 1.4 | 섹션 제목 |
| `--text-subtitle` | 17px | 600 | 1.5 | 카드 서브 |
| `--text-body` | 16px | 400 | 1.7 | 본문 |
| `--text-scripture` | 17px | 400 | 1.85 | 성경 본문 |
| `--text-prayer` | 16px | 400 | 2.0 | 기도문 |
| `--text-chip` | 14px | 500 | 1 | 감정 칩 |
| `--text-button` | 16px | 600 | 1 | 버튼 |
| `--text-small` | 14px | 400 | 1.5 | 날짜 |
| `--text-caption` | 12px | 400 | 1.4 | 캡션 |

---

## 📐 3. 간격 시스템 (미니멀)

| 토큰 | 값 | 용도 |
|---|---|---|
| `--space-2` | 8px | |
| `--space-3` | 12px | |
| `--space-4` | 16px | |
| `--space-5` | 20px | 페이지 좌우 패딩 |
| `--space-6` | 24px | **카드 패딩 / 카드 사이** |
| `--space-8` | 32px | 페이지 상단 |
| `--space-12` | 48px | **섹션 사이** |

---

## 🔲 4. 모서리

| 토큰 | 값 |
|---|---|
| `--radius-md` | 12px |
| `--radius-lg` | 18px (카드) |
| `--radius-pill` | 999px (버튼/칩) |

---

## 🎭 5. 그림자 (최소화)

| 토큰 | 값 |
|---|---|
| `--shadow-none` | none (기본) |
| `--shadow-button` | `0 2px 6px rgba(91, 168, 146, 0.22)` |
| `--shadow-float` | `0 4px 12px rgba(45, 58, 50, 0.06)` |

---

## 🧩 6. 핵심 컴포넌트 예시

### 카드
```css
.card {
  background: #FFFFFF;
  border-radius: 18px;
  padding: 24px;
  margin-bottom: 24px;
}
```

### Primary 버튼 (세이지)
```css
.btn-primary {
  background: #5BA892;
  color: #FFFFFF;
  padding: 15px 32px;
  border-radius: 999px;
  box-shadow: 0 2px 6px rgba(91, 168, 146, 0.22);
  font-weight: 600;
}
```

### 연속일 카드 (그라디언트)
```css
.streak-card {
  background: linear-gradient(135deg, #5BA892 0%, #4A8F7C 100%);
  color: white;
  border-radius: 18px;
  padding: 20px 24px;
}
```

---

## ✅ 이전 버전(초원 스타일)과의 차이

| 영역 | 초원 (이전) | 잔디밭 오후 (현재) |
|---|---|---|
| 메인 색 | 브라운 `#A08566` | **세이지 그린 `#5BA892`** |
| 배경 | 크림 `#EFEAE1` (종이 질감) | **연베이지 `#F7F4ED` (단색)** |
| 분위기 | 따뜻한 종이 | **맑고 친근한 자연** |
| 여백 | 중간 | **넉넉함** (1.5배) |
| 장식 | 종이 질감 배경 | **미니멀, 장식 없음** |
| 감정칩 | 오렌지·틸·퍼플 | **머스터드·세이지·블루그레이** |
| 시간대 | 아침 한정 | **시간 무관 범용** |
