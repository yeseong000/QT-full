# 🖥️ 프론트엔드 가이드

주만나 AI 큐티 프론트엔드 - **iPhone 14/15 Pro 최적화 완료** 🍎

---

## 📂 파일 구조

```
src/
├── index.html                 🏠 홈 화면
├── step-1-scripture.html      📖 1단계: 말씀
├── preview.html               🎨 디자인 시스템 갤러리
├── styles/
│   ├── design-tokens.css      CSS 변수
│   └── common.css             공통 컴포넌트 (iPhone 최적화)
└── scripts/
    ├── storage.js             localStorage 헬퍼
    └── common.js              공통 유틸
```

---

## 🚀 실행 방법

### PC에서 확인

프로젝트 루트에서:
```bash
python3 -m http.server 8000
```

브라우저: http://localhost:8000/src/index.html

→ PC에서 보면 **자동으로 iPhone 프레임**으로 감싸져서 보임

---

## 📱 iPhone 실제 테스트 (가장 중요!)

### ✅ 조건
- **iPhone과 PC가 같은 WiFi 네트워크**에 있어야 함

### 1단계: PC IP 확인

**macOS**:
```bash
ipconfig getifaddr en0
# 예: 192.168.0.15
```

**Windows**:
```bash
ipconfig
# "IPv4 주소" 확인
```

### 2단계: 서버를 외부 접속 허용으로 실행

```bash
# localhost만 → 외부 접속 허용
python3 -m http.server 8000 --bind 0.0.0.0
```

### 3단계: iPhone Safari에서 접속

```
http://192.168.0.15:8000/src/index.html
```
(IP는 실제 PC IP로 변경)

### 4단계 (권장): 홈 화면에 추가

Safari 주소창 아래 공유(📤) → **"홈 화면에 추가"**

→ 탭하면 Safari 주소창 없이 **앱처럼 전체화면** 실행
→ 다이나믹 아일랜드 / 홈바 세이프 에어리어 완벽 적용
→ 이 상태가 최종 사용자가 보게 될 모습 🎯

---

## 🎨 iPhone 최적화 내용

| 항목 | 구현 |
|---|---|
| 다이나믹 아일랜드 대응 | `env(safe-area-inset-top)` |
| 홈바 대응 | `env(safe-area-inset-bottom)` |
| Pull-to-refresh 방지 | `overscroll-behavior-y: contain` |
| 자동 확대 방지 | input `font-size: 16px` 강제 |
| 탭 하이라이트 제거 | `-webkit-tap-highlight-color: transparent` |
| 터치 딜레이 제거 | `touch-action: manipulation` |
| 최소 터치 영역 | 44×44px (Apple HIG) |
| PWA 메타태그 | 홈 화면 추가 시 앱처럼 동작 |
| 최대 폭 | 430px (iPhone 15 Pro Max 실측) |

### 💻 PC에서 보는 모습

481px 이상에서는 **자동으로 iPhone 프레임** 렌더링:
- ⚫ 검정 베젤 + 48px 둥근 모서리
- 📍 다이나믹 아일랜드 시뮬레이션
- 🎯 실제 iPhone 14/15 Pro 비율 (393×852)

---

## 🧩 데이터 경로

HTML은 상대 경로로 데이터 로드:
```javascript
fetch('../data/qt/2026-04-22.json')
```

**반드시 프로젝트 루트에서** 서버 실행 (src/에서 실행 ❌)

---

## 🎯 현재 구현된 기능

### ✅ 홈 (index.html)
- 시간대별 인사말 (5단계)
- "어린양" 기본 닉네임 (설정 변경 가능, '님' 호칭은 저장하지 않음)
- 스트릭 카드 (연속일/총완료)
- 오늘의 말씀 카드
- ⚙️ 설정 모달 (닉네임 변경)

### ✅ 1단계: 말씀 (step-1-scripture.html)
- 진행 단계 점 (1/4)
- 성경 본문
- 폰트 크기 조절 (sm/md/lg)
- 텍스트 드래그 하이라이트
- 하단 네비 (이전/다음)

### 🔜 예정
- 2단계 묵상 · 3단계 적용+기도 · 4단계 감정+메모
- 완료 축하 · 아카이브
- PWA 정식 (Manifest + Service Worker)

---

## 🐛 트러블슈팅

| 문제 | 해결 |
|---|---|
| iPhone에서 접속 안 됨 | 같은 WiFi 확인, PC 방화벽 8000 포트 허용 |
| 회사/공공 WiFi | 기기 간 통신 차단 가능 → 핸드폰 핫스팟 사용 |
| 다이나믹 아일랜드 가림 | 홈 화면 추가한 **PWA 모드**에서만 완벽 작동 |
| 폰트 확대 안 됨 | `user-scalable=no` 설정. 필요 시 `yes`로 변경 |
