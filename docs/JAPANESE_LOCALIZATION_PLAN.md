# 주만나 AI 큐티 — 일본어 현지화 종합 계획

## Context

주만나 AI 큐티 웹앱에 일본어(Japanese) 지원을 추가하는 현지화(Localization) 작업입니다.  
단순 번역이 아니라 **일본 현지 크리스천**을 타겟으로 하는 완전한 현지화가 목표입니다.

- 타겟: 일본에 사는 일본인 크리스천 (기독교 인구 약 1%, 소수 신앙 공동체)
- 성경 본문: API.Bible → 新共同訳 (일본에서 가장 많이 읽히는 번역본)
- 큐티 내용: 오륜교회 주만나(한국어) 크롤링 → GPT 한→일 번역 레이어 추가
- 번역 품질: 2단계 프로세스 (기계번역 초안 → GPT 자연스러운 교정)

---

## 현재 상태 (Before)

| 항목 | 현재 |
|------|------|
| 언어 | 한국어 단일 |
| 성경 | 개역개정 (오륜교회 크롤링) |
| 폰트 | Pretendard Variable |
| i18n | 없음 (HTML/JS에 한국어 하드코딩) |
| GPT 프롬프트 | 한국어 전용 |
| 닉네임 기본값 | "어린양님" |

---

## 결정 사항

1. **타겟**: 일본 현지 크리스천 → 문화적 뉘앙스 완전 현지화 필요
2. **큐티 소스**: 오륜교회 크롤링 유지 + GPT로 한→일 번역
3. **성경 본문**: API.Bible 新共同訳 무료 API 연동
4. **i18n 방식**: 프레임워크 없이 경량 JSON + `data-i18n` 속성 방식 (Vanilla JS)
5. **폰트**: Pretendard → Noto Sans JP (Google Fonts CDN)

---

## 수정 대상 파일

### 기존 수정
- `src/scripts/common.js` — 인사말 함수, 날짜 포맷, i18n 통합
- `src/scripts/storage.js` — 언어 설정 추가, DEFAULT_NICKNAME 다국어
- `src/index.html` — `data-i18n` 속성, 폰트, lang 속성
- `src/step-1-scripture.html` — `data-i18n` 속성, 폰트
- `src/step-2-meditation.html` — `data-i18n` 속성
- `src/step-3-prayer.html` — `data-i18n` 속성
- `src/step-4-record.html` — `data-i18n` 속성
- `src/step-5-done.html` — `data-i18n` 속성
- `src/styles/design-tokens.css` — 폰트 패밀리 변수
- `scripts/generate_ai.py` — 일본어 시스템 프롬프트, 2-pass 교정 규칙
- `scripts/fetch_qt.py` — 언어 파라미터, 번역 레이어 연결

### 신규 생성
- `src/locales/ko.json` — 한국어 문자열 모음
- `src/locales/ja.json` — 일본어 문자열 모음
- `src/scripts/i18n.js` — 언어 로드/전환 헬퍼
- `scripts/translate_qt.py` — 한→일 큐티 번역 스크립트

---

## Phase 1: i18n 인프라 구축

### 1-1. 문자열 추출 → `ko.json`

모든 HTML/JS 파일에서 한국어 하드코딩 문자열을 추출해 `src/locales/ko.json`으로 정리.

```json
{
  "greeting": {
    "dawn": "이른 아침이네요, {{name}}",
    "morning": "좋은 아침이에요, {{name}}",
    "afternoon": "평안한 오후예요, {{name}}",
    "evening": "편안한 저녁이에요, {{name}}",
    "night": "고요한 밤이네요, {{name}}"
  },
  "home": {
    "cta_start": "묵상 시작하기",
    "cta_revisit": "오늘의 묵상 다시 보기",
    "loading": "오늘의 말씀을 준비하고 있어요...",
    "archive_link": "📖 지난 묵상 모아보기"
  },
  "step1": {
    "title": "말씀을 깊이 새겨보세요",
    "version_badge": "개역개정",
    "fab_hint": "마음에 드는 구절을 드래그해 밑줄을 그어보세요"
  },
  "streak": {
    "first": "첫 묵상을 시작해볼까요",
    "restart": "오늘 다시 시작해요",
    "days": "{{n}}일 연속",
    "total": "총 {{n}}회 완료"
  },
  "settings": {
    "title": "설정",
    "nickname_label": "닉네임",
    "background_label": "배경",
    "theme_default": "기본",
    "theme_rose": "로즈",
    "theme_dark": "다크",
    "language_label": "언어"
  },
  "default_nickname": "어린양님"
}
```

주요 추출 위치:
- `src/scripts/common.js:65-75` — 인사말
- `src/scripts/storage.js:6` — DEFAULT_NICKNAME
- `src/index.html:349-557` — 스트릭, 버튼, 로딩, 설정 모달
- `src/step-1-scripture.html:129-154` — 제목, 뱃지, FAB 안내

### 1-2. `src/scripts/i18n.js` 작성

```javascript
const I18n = {
  _strings: {},
  _lang: 'ko',

  async load(lang) {
    const res = await fetch(`/src/locales/${lang}.json`);
    this._strings = await res.json();
    this._lang = lang;
    document.documentElement.lang = lang;
    this._applyAll();
  },

  t(key, vars = {}) {
    const val = key.split('.').reduce((o, k) => o?.[k], this._strings) ?? key;
    return val.replace(/\{\{(\w+)\}\}/g, (_, k) => vars[k] ?? '');
  },

  _applyAll() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = this.t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      el.placeholder = this.t(el.dataset.i18nPlaceholder);
    });
  }
};
```

### 1-3. HTML `data-i18n` 속성 추가

```html
<!-- 기존 -->
<p>좋은 아침이에요, 어린양님</p>

<!-- 변경 후 -->
<p data-i18n="greeting.morning">좋은 아침이에요, 어린양님</p>
```

### 1-4. `storage.js`에 언어 설정 추가

```javascript
// localStorage key: settings.language
// 기본값: 'ko', 일본어: 'ja'
Storage.getLanguage = () => Storage.get('settings.language') ?? 'ko';
Storage.setLanguage = (lang) => Storage.set('settings.language', lang);
```

---

## Phase 2: 일본어 번역 1단계 (기계번역 초안)

GPT에게 `ko.json` 전체를 한꺼번에 번역 요청.

### 번역 프롬프트 구조

```
시스템: 당신은 일본 기독교 문화에 정통한 번역가입니다.
대상: 일본 현지 크리스천을 위한 묵상 앱 UI 문자열
규칙:
- 경어체 (です/ます 형) 일관 사용
- 한국식 직역 금지
- 성경 용어: 御言葉(みことば), 主(しゅ), 神様(かみさま), 恵み(めぐみ)
- 닉네임 기본값: "子羊さん" (어린양님 → 子羊さん)
- 인사말은 자연스러운 일본어로 (직역 금지)
```

### 인사말 번역 예시

| 한국어 | 일본어 (목표) |
|--------|--------------|
| "이른 아침이네요, {{name}}" | "おはようございます、{{name}}" |
| "좋은 아침이에요, {{name}}" | "おはようございます、{{name}}" |
| "평안한 오후예요, {{name}}" | "こんにちは、{{name}}" |
| "편안한 저녁이에요, {{name}}" | "こんばんは、{{name}}" |
| "고요한 밤이네요, {{name}}" | "夜更かしですね、{{name}}" |

### 날짜 포맷 변경

```javascript
// 한국어
formatKoreanDate() → "2026년 4월 22일 수요일"

// 일본어
formatJapaneseDate() → "2026年4月22日 水曜日"
// (타임존은 JST = KST = UTC+9로 동일, 변경 불필요)
```

---

## Phase 3: 일본어 번역 2단계 (GPT 자연스러운 교정)

### 교정 Pass 1: 자연스러운 표현 검수

```
체크포인트:
1. 한국어 직역 잔재 제거 ("말씀" → "御言葉" or "み言葉")
2. 시간대 인사말 — 일본식 표현으로 (직역 금지)
3. 존댓말 일관성 (です/ます 체 혼용 없이)
4. 묵상 앱 특유 표현 자연화 ("묵상 시작하기" → "デボーションを始める")
```

### 교정 Pass 2: 크리스천 용어 통일성

```
표준 용어 목록:
- 말씀 → 御言葉 (みことば)
- 주님 → 主 (しゅ) / 主よ
- 하나님 → 神様 (かみさま)
- 은혜 → 恵み (めぐみ)
- 묵상 → デボーション or 黙想
- 큐티 → デボーション (QT는 일본에서 덜 통용)
- 기도 → お祈り / 祈り
- 스트릭 → 連続記録
- 어린양님 → 子羊さん
```

---

## Phase 4: 성경 본문 연동 (API.Bible 新共同訳)

### API.Bible 연동 방식

```python
# scripts/fetch_bible_ja.py (신규)
import requests

API_KEY = os.getenv("BIBLE_API_KEY")  # API.Bible 무료 키
BASE_URL = "https://api.scripture.api.bible/v1"

# 新共同訳 Bible ID (API.Bible 내 일본어 新共同訳)
JA_BIBLE_ID = "..."  # 실제 사용 전 API 콘솔에서 확인 필요

def fetch_verses_ja(book, chapter, start_verse, end_verse):
    """개역개정 크롤링 구조와 동일한 형태로 新共同訳 반환"""
    passage_id = f"{book}.{chapter}.{start_verse}-{book}.{chapter}.{end_verse}"
    res = requests.get(
        f"{BASE_URL}/bibles/{JA_BIBLE_ID}/passages/{passage_id}",
        headers={"api-key": API_KEY},
        params={"content-type": "text", "include-verse-numbers": True}
    )
    return parse_response(res.json())
```

### 데이터 구조 변경

```json
// data/qt/2026-04-22.json (현재: 한국어만)
{
  "date": "2026-04-22",
  "scripture_ref": "룻기 1:15-22",
  "verses": [{"number": 15, "text": "나오미가 또 이르되..."}]
}

// 변경 후: 다국어 포함
{
  "date": "2026-04-22",
  "scripture_ref": { "ko": "룻기 1:15-22", "ja": "ルツ記 1:15-22" },
  "verses": {
    "ko": [{"number": 15, "text": "나오미가 또 이르되..."}],
    "ja": [{"number": 15, "text": "ナオミはまた言った..."}]
  }
}
```

### 저작권 주의사항

- **新共同訳**: 日本聖書協会 저작권. API.Bible을 통한 비상업적 사용은 가능.
- **앱이 상업화될 경우**: 日本聖書協会에 별도 허가 필요.
- **현실적 대안**: 저작권 만료된 번역본(문어역 등)이나 공개 도메인 일본어 성경 사용 고려.

---

## Phase 5: 큐티 콘텐츠 번역 레이어

### `scripts/translate_qt.py` (신규)

```python
# fetch_qt.py 실행 후 → translate_qt.py 실행
# data/qt/YYYY-MM-DD.json (한국어) → data/qt/ja/YYYY-MM-DD.json (일본어)

TRANSLATION_SYSTEM_PROMPT = """
당신은 한국어 기독교 묵상 자료를 일본 크리스천을 위해 번역하는 전문가입니다.

번역 규칙:
- 목표 독자: 일본 현지 크리스천 (개신교)
- 문체: 정중하고 따뜻한 です/ます 체
- 한국식 표현 직역 금지 → 일본 크리스천에게 자연스러운 표현으로
- 성경 용어: 御言葉, 主, 神様, 恵み 통일 사용
- 한국 교회 특유 표현(아멘, 할렐루야 등)은 그대로 유지
- 구절 제목/내용은 新共同訳 표현에 맞게 조정
"""
```

### GitHub Actions 파이프라인 수정

```yaml
# .github/workflows/daily_qt.yml (수정)
steps:
  - name: Fetch QT (Korean)
    run: python scripts/fetch_qt.py
  
  - name: Fetch Bible (Japanese - API.Bible)
    run: python scripts/fetch_bible_ja.py
    env:
      BIBLE_API_KEY: ${{ secrets.BIBLE_API_KEY }}
  
  - name: Translate QT content (KO → JA)
    run: python scripts/translate_qt.py
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  
  - name: Generate AI content (Korean)
    run: python scripts/generate_ai.py --lang ko
  
  - name: Generate AI content (Japanese)
    run: python scripts/generate_ai.py --lang ja
```

---

## Phase 6: GPT 프롬프트 일본어화

### `scripts/generate_ai.py` 수정사항

#### 언어 파라미터 추가

```python
def generate_ai_content(qt_data: dict, lang: str = "ko") -> dict:
    system_prompt = get_system_prompt(lang)
    user_prompt = build_user_prompt(qt_data, lang)
    ...
```

#### 일본어 시스템 프롬프트

```python
JA_SYSTEM_PROMPT = """
あなたは温かく誠実な牧師であり、同時に日本人の心に寄り添う
信仰のメンターです。聖書を深く愛し、日常の言葉で
神の御言葉を伝えることが得意です。

【話し方の原則】
- 丁寧語（です/ます体）を統一して使用
- 説教調・訓戒的にならず、共に考えるトーン
- 一文を短く区切る
- 神学的な専門用語は最小限に。使う時は必ず平易な言葉で補足
- 日本のキリスト教コミュニティが親しむ表現を使用
"""
```

#### 일본어 금지 표현 목록

```python
JA_FORBIDDEN_WORDS = [
    "皆さん",     # 한국어 "여러분" 직역
    "~しなければなりません",  # 강압적 표현
    "必ずしなければ",
    "与えてあげます",  # 시혜적 표현
    "恵んであげます",
]
```

#### 2-pass 교정 — 일본어 적용 규칙

| 한국어 규칙 | 일본어 대응 |
|------------|------------|
| "나/내" → "저/제" | "俺/僕" → "私" |
| "베풀겠습니다" 금지 | "与えてあげます" 금지 |
| "여러분" 금지 | "皆さん" 금지 |
| 시작 단어 다양성 | 3개 항목 문두 단어 반복 금지 |

#### 기도문 형식 차이

```
한국 교회 기도문: "주님, / 오늘 이 말씀으로..."
일본 교회 기도문: "主よ、/ 今日、このみ言葉によって..."

→ 일본식 기도문은 조금 더 격식 있고, 漢字 표현 선호
```

---

## Phase 7: 폰트 + 언어 전환 UI

### 폰트 변경

```html
<!-- 기존: Pretendard (한국어 최적화) -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/.../pretendardvariable.css">

<!-- 변경 후: 언어별 분기 -->
<!-- ko → Pretendard Variable 유지 -->
<!-- ja → Noto Sans JP (Google Fonts) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
```

```css
/* design-tokens.css 수정 */
:root {
  --font-sans: 'Pretendard Variable', Pretendard, sans-serif;
}

:root[lang="ja"] {
  --font-sans: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', Meiryo, sans-serif;
  --text-scripture: 18px; /* 한자 가독성 위해 1px 증가 */
  --line-height-scripture: 1.9; /* 일본어 행간 넓게 */
}
```

### 설정 모달 언어 선택 UI 추가

```html
<!-- src/index.html 설정 모달 내 추가 -->
<div class="setting-row">
  <span data-i18n="settings.language_label">언어</span>
  <div class="language-toggle">
    <button class="lang-btn active" data-lang="ko">🇰🇷 한국어</button>
    <button class="lang-btn" data-lang="ja">🇯🇵 日本語</button>
  </div>
</div>
```

```javascript
// 언어 전환 로직 (common.js 또는 i18n.js)
document.querySelectorAll('.lang-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const lang = btn.dataset.lang;
    Storage.setLanguage(lang);
    await I18n.load(lang);
    // 페이지 새로고침 없이 동적 교체
  });
});
```

---

## 번역 시 문화적 주의사항

### 일본 크리스천 문화 특수성

1. **소수 신앙 공동체** (인구의 ~1%)
   - 과도한 전도적 표현 지양 → 더 개인적/묵상적 톤 유지
   - "여러분께 전하고 싶어요" 같은 표현 → 삭제 또는 내면 지향으로 변환

2. **묵상 호칭 용어**
   - "큐티(QT)" → 일본에서는 "デボーション(Devotion)"이 더 통용
   - "주만나" → 일본 고유 명칭이 없으므로 그대로 사용하거나 "今日のみ言葉"로

3. **기도문 스타일**
   - 한국 교회: 감정적, 반복적, 직접적
   - 일본 교회: 차분하고 격식 있는 문어체 기도 선호

4. **감정 칩 번역**

| 한국어 | 일본어 | 비고 |
|--------|--------|------|
| 평온함 | 平和 | |
| 깨달음 | 気づき | |
| 성찰 | 内省 | |
| 감사 | 感謝 | |
| 도전 | チャレンジ | |
| 위로 | 慰め | |
| 기쁨 | 喜び | |
| 결심 | 決意 | |
| 간구 | 切なる祈り | 직역 불가, 의역 필요 |

5. **성경 구절 참조 형식**
   - 한국어: "룻기 1:15"
   - 일본어: "ルツ記 1章15節" (章/節 표기 일반적)

---

## 검증 방법

1. **언어 전환 동작 확인**
   - 설정 모달에서 🇯🇵 日本語 선택 후 모든 UI 문자열이 즉시 교체되는지
   - localStorage에 `settings.language = "ja"` 저장 및 새로고침 후 유지 확인

2. **성경 본문 확인**
   - API.Bible 新共同訳 응답이 정상적으로 표시되는지
   - 구절 번호 형식 (1章15節) 맞게 표시되는지

3. **번역 품질 검수**
   - 한국어 직역 잔재 없는지 (특히 인사말, 버튼 텍스트)
   - 크리스천 용어 통일성 (御言葉, 主, 神様 등)
   - 존댓말 일관성 (です/ます 체)

4. **폰트 렌더링 확인**
   - 일본어 선택 시 Noto Sans JP 적용 확인
   - 모바일 430px 기준 성경 본문 가독성 (한자+가나 혼용)

5. **GPT 생성 콘텐츠 품질**
   - 일본어 묵상 콘텐츠가 자연스러운지
   - 기도문 스타일이 일본 교회 문화에 맞는지

6. **추가 비용 추정 (GPT-4o-mini 기준)**
   - 기존: 한국어 AI 생성만 → **약 550원/년** (하루 약 1.5원)
   - 추가: 한→일 번역 1회 + 일본어 AI 생성 1회 → **약 +1,100원/년**
   - 합계: **약 1,650원/년** (현재의 약 3배이지만 절대 금액은 매우 저렴)

---

## 구현 순서 요약

```
Phase 1  ko.json + ja.json + i18n.js + data-i18n 속성 추가 (인프라)
    ↓
Phase 2  ja.json 1단계 번역 (GPT 기계번역 초안)
    ↓
Phase 3  ja.json 2단계 교정 (GPT 자연스러운 교정 + 크리스천 용어 검수)
    ↓
Phase 4  API.Bible 新共同訳 연동 (fetch_bible_ja.py)
    ↓
Phase 5  translate_qt.py 작성 (한→일 큐티 번역 레이어)
    ↓
Phase 6  generate_ai.py 일본어 지원 추가 (--lang ja 파라미터)
    ↓
Phase 7  폰트 + 설정 모달 언어 전환 UI
```

---

## 참고 자료 (웹 검색 출처)

- [聖書おすすめの翻訳（種類比較）](https://jesus153blog.com/bible-translation/)
- [日本聖書協会 - 聖書の選び方](https://www.bible.or.jp/online/how-to-choose.html)
- [日本聖書協会 - ご利用規約](https://www.bible.or.jp/conditions.html)
- [API.Bible Portal](https://portal.dev.api.bible/)
- [jpn.bible (GitHub 오픈소스)](https://github.com/tadd/jpn.bible)
- [ディヴォーション (キリスト教) - Wikipedia](https://ja.wikipedia.org/wiki/%E3%83%87%E3%82%A3%E3%83%B4%E3%82%A9%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3_(%E3%82%AD%E3%83%AA%E3%82%B9%E3%83%88%E6%95%99))
- [Noto Sans JP - Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+JP)
- [vanilla-i18n (경량 i18n 라이브러리)](https://github.com/thealphadollar/vanilla-i18n)
