# UI_QR_MODAL — QR 공유 모달 명세

> 인덱스 화면에서 우측 상단 QR 아이콘 탭 시 오픈.
> 의존: `scripts/qr.js` (Vanilla JS, MIT, 외부 의존성 0).

---

## 1. 마크업 구조

```
#qrModal (.modal-backdrop)
└─ .modal-sheet
   ├─ .modal-drag-handle              ← 스와이프 다운 영역
   └─ .modal-sheet__scroll
      └─ .qr-modal-content
         ├─ h2.qr-modal__title         "큐티 묵상"
         ├─ p.qr-modal__desc           "QR을 스캔하면 사이트로 이동해요."
         ├─ #qrCard (.qr-card)         240×240, 흰 배경, 16px 패딩
         │  └─ <svg> (JS 동적 생성)
         └─ .qr-url-row
            ├─ #qrUrlText (.qr-url-text)   도메인만
            └─ button#qrCopyBtn (.qr-copy-btn) "복사"
```

---

## 2. QR 코드 스펙

| 항목 | 값 |
|---|---|
| 라이브러리 | `scripts/qr.js` (Vanilla, MIT) |
| 호출 | `QRCode.toSVG(url, { size: 240, margin: 0 })` |
| 색상 | `dark: #1A1D1B`, `light: #FFFFFF` (대비 최대) |
| 가운데 로고 | **없음** (인식률 우선) |
| 외곽 패딩 | `.qr-card`의 `padding: 16px`로 처리 (quiet zone) |
| URL 소스 | `<meta property="og:url">` (단일 진실 공급원) |

---

## 3. URL 표시 정책

- **QR**은 풀 URL 인코딩 (`https://hainaqt.vercel.app`)
- **화면 텍스트**는 도메인만 (`hainaqt.vercel.app`) — 모바일 가독성
- **복사 버튼**도 화면 표시값 기준 (도메인만)

---

## 4. 인터랙션

| 액션 | 동작 |
|---|---|
| QR 아이콘 탭 (`#qrShareBtn`) | `openQrModal()` — 슬라이드 업 |
| 백드롭(밖) 탭 | `closeQrModal()` |
| 핸들 스와이프 다운 | `setupQrModalSwipeDown()` — 80px 또는 빠른 속도 시 닫힘 |
| 복사 버튼 탭 | `navigator.clipboard.writeText()` → 1.5초간 "복사됨" 표시 후 원복 |

---

## 5. 핵심 JS 함수

| 함수 | 역할 |
|---|---|
| `openQrModal()` | URL 가져오기 → QR SVG 생성 → 모달 오픈 |
| `closeQrModal()` | 모달 닫기 + 시트 transform 초기화 |
| `getShareUrl()` | `og:url` 메타 → fallback `window.location.origin` |
| `setupQrModalSwipeDown()` | 핸들 pointer 이벤트로 스와이프-닫기 |

---

## 6. 디자인 의도

- **장식 없음** — 카메라 인식률이 가장 중요. 가운데 로고/그라디언트 없음.
- **대비 최대** — 순수 검정/흰색. 색조 검정 사용 X.
- **버튼 1개** — 복사만. 저장/공유 등 추가 안 함 (선택지 부담 제거).
- **상단 핸들 + 우측 X 없음** — 핸들 스와이프 다운만으로 충분. 다른 사람에게 폰을 들이밀 때 X 버튼이 작아 오히려 누르기 어려움.

---

## 7. 다른 화면에서 재사용 시

이 모달은 인덱스 외 화면에서도 재호출 가능. 단:
- 마크업 블록 + 함수 4개를 그대로 복제하지 말고, **모듈화 검토** 필요 (Phase 3 후보)
- 현재는 인덱스 전용으로 `index.html` 안에 인라인 정의됨
