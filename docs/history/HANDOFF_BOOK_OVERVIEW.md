# HANDOFF: 책 살펴보기 카드 리팩토링

> 이 문서는 Claude Code Web 또는 VS Code Claude Code 확장이 참조하는 작업 사양서입니다.
> 작업 진행 전 **반드시** 별도 검증 프롬프트(Phase 1~4)를 따라야 합니다.

---

## 0. 최종 결정 사항 요약

| 항목 | 결정 |
|---|---|
| 카드 제목 | `○○의 흐름` → **`○○ 살펴보기`** |
| 이모지 처리 | **모든 묵상 카드(5종) 이모지 제거** |
| 4파트 라벨 | 저자 / 시기 / 기록 장소와 대상 / 핵심 내용 |
| 톤 | 단답 가능한 곳은 단답("사도바울"), 서술 필요한 곳만 서술 |
| 디자인 | C 정의 목록식 (좌 라벨 92px / 우 본문, dl grid) |
| 데이터 구조 | `book_overview`: string → object `{author, date, place, core}` |
| 옛 데이터 | 재생성 ✗ — 프론트엔드 폴백으로 string도 계속 표시 |

---

## 1. 변경 사항 요약 표

| 파일 | 위치 | 종류 |
|---|---|---|
| A-1 | `scripts/generate_ai.py` `build_user_prompt()` #3 | 교체 |
| A-2 | `scripts/generate_ai.py` JSON 출력 예시 | 교체 |
| A-3 | `scripts/generate_ai.py` `_mock_ruth_1()` | 교체 |
| A-4 | `scripts/generate_ai.py` `_mock_generic()` | 교체 |
| A-5 | `scripts/generate_ai.py` `validate()` | 교체 |
| B-1 | `src/qt/step-2-meditation.html` `<style>` 내 | CSS 추가 |
| B-2 | `src/qt/step-2-meditation.html` 카드 HTML 5곳 | 이모지 제거 + 책 카드 텍스트 |
| B-3 | `src/qt/step-2-meditation.html` `renderBookContext()` | 교체 |
| C-1 (선택) | `docs/DATA_SCHEMA.md` book_overview 스키마 | 갱신 |

---

## 2. 파일 A: `scripts/generate_ai.py`

### A-1. `build_user_prompt()` 요구사항 #3 교체

**변경 전:**
```python
3. book_overview: 이 책({qt_data['book_name']})의 전체 배경과 주제만 설명. 2~3문장. 오늘 구절에 대한 언급 절대 금지.
```

**변경 후:**
```python
3. book_overview: 이 책({qt_data['book_name']}) 전체에 대한 소개. 오늘 본문이나 특정 구절은 절대 언급하지 말 것.
   다음 4개 필드를 가진 **객체(JSON object)** 로 출력:

   - "author" (저자): 누가 썼다고 전해지는지. 가능하면 한두 어절로 짧게 (예: "사도바울",
     "전통적으로 사무엘로 전해짐"). 저자 논쟁이 있는 책(히브리서, 베드로후서, 모세오경,
     이사야, 욥기 등)은 "알려져 있지 않음", "여러 견해가 있음" 같은 완충 표현 필수. 단정 금지.

   - "date" (시기): 대략의 기록 시기를 한 줄로 짧게
     (예: "AD 60~63년경 추정", "사사 시대 후 후대에 정리"). 정확한 연도 단정 금지.

   - "place" (기록 장소와 대상): 어디서 누구를 위해 쓰였는지 자연스러운 한 문장
     (예: "로마의 감옥에서 썼으며 에베소에 있는 그리스도인을 위해 씀.").
     알 수 없으면 "정확한 기록 장소는 알려져 있지 않습니다" 식으로 처리.

   - "core" (핵심 내용): 책 전체 줄거리·핵심 메시지. 1~2문장. 특정 구절 인용 금지.

   톤: 한국어, 존댓말, 따뜻한 ~이에요/~습니다 체. 신학용어는 풀어 설명.
   교단 편향·논쟁적 해석 금지.
```

### A-2. JSON 출력 예시 교체

**변경 전:**
```python
"book_overview": "책 전체 배경 설명 (오늘 구절 언급 금지)",
```

**변경 후:**
```python
"book_overview": {
  "author": "저자 (한두 어절 또는 회피 어구)",
  "date": "대략적 시기 한 줄",
  "place": "어디서 누구를 위해 쓰였는지 (한 문장)",
  "core": "책 전체 줄거리·메시지 (1~2문장, 특정 구절 인용 금지)"
},
```

### A-3. `_mock_ruth_1()` book_overview 교체

**변경 전:**
```python
"book_overview": "룻기는 사사시대라는 혼란의 시기에 피어난 한 이방 여인의 헌신과 회복의 이야기입니다. 짧지만 강렬한 이 책은 '상실'에서 '회복'으로 이어지는 하나님의 섬세한 인도를 보여줍니다. 훗날 룻은 다윗의 증조모가 되어 예수 그리스도의 족보에 오르게 됩니다.",
```

**변경 후:**
```python
"book_overview": {
    "author": "전통적으로 사무엘로 전해짐",
    "date": "사사 시대 이야기, 후대에 정리됨",
    "place": "이스라엘 백성을 위해 쓰였으며, 정확한 기록 장소는 알려져 있지 않습니다.",
    "core": "모압 여인 룻이 시어머니를 따라 베들레헴에 와 보아스와 가정을 이루는 이야기로, 평범한 삶 속에서 일하시는 하나님의 손길을 보여줍니다."
},
```

### A-4. `_mock_generic()` book_overview 교체

**변경 전:**
```python
"book_overview": f"{book}은 구약/신약 성경의 한 부분으로, 하나님의 구원 역사를 보여주는 중요한 책입니다. 전체 맥락을 이해하면 본문의 의미가 더 풍성해집니다.",
```

**변경 후:**
```python
"book_overview": {
    "author": f"{book}의 저자에 대해서는 여러 견해가 있습니다",
    "date": f"{book}이 다루는 시대 이후 후대에 정리된 것으로 전해집니다",
    "place": "당시 하나님의 백성을 위해 기록되었습니다.",
    "core": f"{book}은 하나님과 그 백성 사이의 관계, 그 안에서 일하시는 하나님의 손길을 보여줍니다."
},
```

### A-5. `validate()` book_overview 검증 강화

**변경 전:**
```python
# book_overview / passage_intro 존재 확인
if not ai_data.get("book_overview"):
    warnings.append("book_overview 필드 없음")
if not ai_data.get("passage_intro"):
    warnings.append("passage_intro 필드 없음")
```

**변경 후:**
```python
# book_overview 검증: 객체(4필드)이며 옛 문자열도 폴백으로 허용
bo = ai_data.get("book_overview")
if not bo:
    warnings.append("book_overview 필드 없음")
elif isinstance(bo, dict):
    for key in ("author", "date", "place", "core"):
        if not bo.get(key):
            warnings.append(f"book_overview.{key} 비어 있음")
elif isinstance(bo, str):
    if len(bo) < 30:
        warnings.append(f"book_overview 문자열이 너무 짧음 ({len(bo)}자)")

# passage_intro 존재 확인
if not ai_data.get("passage_intro"):
    warnings.append("passage_intro 필드 없음")
```

---

## 3. 파일 B: `src/qt/step-2-meditation.html`

### B-1. CSS 추가

**위치:** `<style>` 블록 안, `</style>` 직전 ("로딩/에러/빈 상태" 블록 다음)

**추가 코드:**
```css
/* 책 살펴보기 카드 (정의 목록식 dl grid) */
.book-overview-list {
  display: grid;
  grid-template-columns: 92px 1fr;
  row-gap: 14px;
  column-gap: 16px;
  margin: 0;
}
.book-overview-list dt {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent-sage-text);
  padding-top: 2px;
  letter-spacing: 0.02em;
}
.book-overview-list dd {
  margin: 0;
  font-size: var(--text-body);
  line-height: 1.65;
  color: var(--text-body);
}
/* 작은/큰 폰트 모드 대응 */
html[data-font-size="sm"] .book-overview-list { grid-template-columns: 80px 1fr; }
html[data-font-size="lg"] .book-overview-list { grid-template-columns: 100px 1fr; }
/* 다크/밤 모드에서 라벨 대비 보강 */
html[data-time-slot="night"] .book-overview-list dt { color: #A8D5C2; }
```

### B-2. 카드 HTML 5곳 — 이모지 모두 제거 + 책 카드 텍스트 변경

#### ① 책 살펴보기 카드 (가장 큰 변경)

**변경 전:**
```html
<!-- ① 책 맥락 카드 (큰 그림 먼저) -->
<section class="meditation-card" id="bookContextCard" style="display:none;">
  <h2 class="meditation-card__title">
    <span class="meditation-card__icon">📚</span>
    <span><span id="bookContextTitle">책</span>의 흐름</span>
  </h2>
  <div class="prose" id="bookContext"></div>
</section>
```

**변경 후:**
```html
<!-- ① 책 살펴보기 카드 (큰 그림 먼저) -->
<section class="meditation-card" id="bookContextCard" style="display:none;">
  <h2 class="meditation-card__title">
    <span><span id="bookContextTitle">책</span> 살펴보기</span>
  </h2>
  <div id="bookContext"></div>
</section>
```

#### ② 등장인물 카드

**변경 전:**
```html
<h2 class="meditation-card__title">
  <span class="meditation-card__icon">👥</span>
  말씀 속 인물들
</h2>
```

**변경 후:**
```html
<h2 class="meditation-card__title">
  말씀 속 인물들
</h2>
```

#### ③ 깊은 묵상 카드

**변경 전:**
```html
<h2 class="meditation-card__title">
  <span class="meditation-card__icon">🌿</span>
  깊은 묵상
</h2>
```

**변경 후:**
```html
<h2 class="meditation-card__title">
  깊은 묵상
</h2>
```

#### (폴백) 말씀 속 장면 카드

**변경 전:**
```html
<h2 class="meditation-card__title">
  <span class="meditation-card__icon">✨</span>
  말씀 속 장면
</h2>
```

**변경 후:**
```html
<h2 class="meditation-card__title">
  말씀 속 장면
</h2>
```

#### (폴백) 구절 해설 카드

**변경 전:**
```html
<h2 class="meditation-card__title">
  <span class="meditation-card__icon">💡</span>
  구절 깊이 들여다보기
</h2>
```

**변경 후:**
```html
<h2 class="meditation-card__title">
  구절 깊이 들여다보기
</h2>
```

> **참고:** `.meditation-card__icon` CSS 클래스 정의는 **그대로 두세요**. 다른 화면(step-3 등)에서 쓰일 수 있고, 안 쓰여도 무해합니다.

### B-3. `renderBookContext()` 함수 교체

**변경 전:**
```javascript
function renderBookContext(text) {
  if (!text) return;
  document.getElementById('bookContextCard').style.display = '';
  document.getElementById('bookContext').textContent = text;
}
```

**변경 후:**
```javascript
function renderBookContext(value) {
  if (!value) return;
  document.getElementById('bookContextCard').style.display = '';
  const target = document.getElementById('bookContext');
  target.replaceChildren();
  target.classList.remove('prose');

  // 신 스키마: 객체 {author, date, place, core}
  if (typeof value === 'object' && !Array.isArray(value)) {
    const LABELS = {
      author: '저자',
      date:   '시기',
      place:  '기록 장소와 대상',
      core:   '핵심 내용'
    };
    const dl = document.createElement('dl');
    dl.className = 'book-overview-list';
    ['author', 'date', 'place', 'core'].forEach(key => {
      if (!value[key]) return;
      const dt = document.createElement('dt');
      dt.textContent = LABELS[key];
      const dd = document.createElement('dd');
      dd.textContent = value[key];
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    target.appendChild(dl);
    return;
  }

  // 옛 스키마: 문자열 (book_overview string 또는 book_context fallback)
  target.classList.add('prose');
  target.textContent = String(value);
}
```

> **`loadAI()` 내 `bookOverview` 분기 로직(`const _ctxParts = ...` 줄들)은 수정 불필요** — `ai.book_overview`가 객체든 문자열이든 그대로 넘기면 `renderBookContext()`가 알아서 분기 처리.

---

## 4. 파일 C: `docs/DATA_SCHEMA.md` (선택, 권장)

### C-1. book_overview 스키마 갱신

**변경 전:**
```json
"book_overview": "책 전체 배경과 주제 (오늘 구절 언급 없음, 2~3문장)",
```

**변경 후:**
```json
"book_overview": {
  "author": "저자 (한두 어절 또는 회피 어구)",
  "date": "기록 시기 한 줄",
  "place": "기록 장소와 대상 (한 문장)",
  "core": "책 전체 핵심 내용 (1~2문장)"
},
```

기존 "하위 호환" 노트에 다음 줄 추가:
> 옛 `book_overview`가 문자열 형식인 JSON도 프론트엔드가 자동으로 prose 형태로 폴백 렌더합니다.

---

## 5. 사후 검증

### 5-1. Mock 모드
```bash
python scripts/generate_ai.py --mock --dry-run
```
출력의 `book_overview`가 객체이고 4필드 모두 있는지.

### 5-2. 실 API (선택)
```bash
python scripts/generate_ai.py --date <YYYY-MM-DD> --dry-run
```
다양한 책(에베소서·룻기·히브리서) 본문 날짜로 1~2회 실행 → 단답/서술 균형 + 회피 어구 정상 동작 확인.

### 5-3. 화면 테스트 (사용자 직접)
```bash
python -m http.server 8000
```
- `http://localhost:8000/src/qt/step-2-meditation.html?date=<오늘>` (새 카드 확인)
- `http://localhost:8000/src/qt/step-2-meditation.html?date=<옛 날짜>` (string 폴백 동작 확인)
- 5개 카드 모두 이모지 없음, 책 카드 제목 "○○ 살펴보기", 좌 라벨/우 본문 정렬 양식 확인

---

## 6. 절대 금지 사항

- 인수인계 사양과 다른 변경 추가 금지 (예: 라벨명 임의 변경, 색상 변경)
- 다른 카드 구조 손대지 말 것 (5단 호흡·등장인물·기도 등)
- React/Vue/Tailwind 도입 금지 (Vanilla JS + 커스텀 CSS만)
- `.env`, `data/*.json` 커밋 금지
- 옛 데이터 일괄 재생성 금지

---

*마지막 업데이트: 2026-05-12*
