# 💾 데이터 스키마 & 저장소 설계

프로젝트에서 사용하는 모든 데이터 구조와 localStorage 키 설계를 정리합니다.

---

## 📁 전체 데이터 구조

```
📂 프로젝트 데이터
│
├── 🖥️ 서버 측 (GitHub 리포지토리 내 JSON 파일)
│   ├── /data/qt/YYYY-MM-DD.json       (원본 QT 본문)
│   ├── /data/ai/YYYY-MM-DD.json       (AI 생성 묵상)
│   └── /data/manifest.json            (전체 날짜 인덱스)
│
└── 📱 클라이언트 측 (브라우저 localStorage)
    ├── user.*                         (사용자 정보)
    ├── settings.*                     (설정)
    ├── streak.*                       (연속일)
    └── records.YYYY-MM-DD.*           (일별 기록)
```

---

## 🖥️ 서버 측 데이터

### 1. `/data/qt/YYYY-MM-DD.json` (원본 QT)

크롤러가 매일 저장하는 오륜교회 주만나 본문 원본 데이터.

```json
{
  "date": "2026-04-22",
  "date_label": "04.22수요일",
  "title": "회복으로 나아가라",
  "subtitle": "나오미와 함께 가기로 결심한 룻",
  "scripture_ref": "룻기 1:15-22",
  "book_name": "룻기",
  "chapter": 1,
  "verses_start": 15,
  "verses_end": 22,
  "verses": [
    {
      "number": 15,
      "text_kr": "나오미가 또 이르되...",
      "text_en": "\"Look,\" said Naomi..."
    }
  ],
  "oryun_questions": [
    "하나님께 속하기 위해 어떤 노력을 할 수 있습니까?"
  ],
  "source_url": "https://oryun.org/life/?menu=248",
  "fetched_at": "2026-04-22T05:00:00+09:00"
}
```

### 2. `/data/ai/YYYY-MM-DD.json` (AI 묵상)

GPT가 생성한 묵상 콘텐츠. 생성 프롬프트는 `scripts/generate_ai.py`, 운영 메모는 `AI_PROMPT.md` 참고.

```json
{
  "date": "2026-04-22",
  "scenes": ["...", "...", "...", "...", "..."],
  "characters": [{ "name": "...", "description": "..." }],
  "book_overview": {
    "author": "저자 (한두 어절 또는 회피 어구)",
    "date": {
      "covered": "다룬 시대 (선택, 신약 서신 등은 null)",
      "written": "기록 시기 한 줄 (필수)"
    },
    "place": "기록 장소와 대상 (한 문장, 명사형 종결)",
    "core": "책 전체 핵심 내용 (1~2문장, 체언 종결)"
  },
  "passage_intro": "오늘 본문이 이 책의 흐름 안에서 어디에 위치하는지 (1문장)",
  "verse_commentary": "...",
  "application": [{ "statement": "...", "detail": "..." }],
  "prayer": ["...", "...", "..."],
  "generated_at": "2026-04-22T05:00:30+09:00",
  "model": "gpt-4o-mini"
}
```

> **하위 호환:** 구 스키마(`book_context`, `core_summary`)로 생성된 기존 JSON은 변경하지 않아도 됩니다.
> 프론트엔드에서 새 필드가 없을 경우 자동으로 구 필드에서 분기 처리합니다.
> 신규 `generate_ai.py` 실행분부터 새 필드가 생성됩니다.
> 옛 `book_overview`가 문자열 형식인 JSON도 프론트엔드가 자동으로 prose 형태로 폴백 렌더합니다.
> 옛 `book_overview.date`가 문자열 형식인 경우도 프론트엔드가 단일 줄로 폴백 렌더합니다.

### 3. `/data/manifest.json` (인덱스)

아카이브에서 사용할 전체 날짜 인덱스.

```json
{
  "updated_at": "2026-04-22T05:00:30+09:00",
  "total_count": 142,
  "entries": [
    {
      "date": "2026-04-22",
      "scripture_ref": "룻기 1:15-22",
      "title": "회복으로 나아가라"
    },
    {
      "date": "2026-04-21",
      "scripture_ref": "룻기 1:6-14",
      "title": "돌아가야 할 때"
    }
  ]
}
```

---

## 📱 클라이언트 측 (localStorage)

### 🔑 키 명명 규칙

```
영역.서브영역.세부키
예시: user.name, records.2026-04-22.underlines
```

### 📋 전체 키 목록

#### 1. 사용자 정보 (`user.*`)

| 키 | 값 타입 | 예시 | 설명 |
|---|---|---|---|
| `user.name` | string | `"정국"` | 첫 방문 시 입력 |
| `user.joined_at` | ISO date | `"2026-03-01"` | 가입일 |

#### 2. 설정 (`settings.*`)

| 키 | 값 타입 | 기본값 | 설명 |
|---|---|---|---|
| `settings.theme` | `"light"` \| `"dark"` | `"light"` | 테마 |
| `settings.fontSize` | `"sm"` \| `"md"` \| `"lg"` | `"md"` | 폰트 크기 |
| `settings.background` | string | `"paper-cream"` | 선택한 배경 ID |
| `settings.pwa.promptShown` | boolean | `false` | PWA 설치 안내 표시 여부 |

#### 3. 연속일/통계 (`streak.*`)

| 키 | 값 타입 | 예시 | 설명 |
|---|---|---|---|
| `streak.current` | number | `15` | 현재 연속일 |
| `streak.longest` | number | `42` | 최장 연속일 |
| `streak.lastDate` | ISO date | `"2026-04-22"` | 마지막 완료일 |
| `streak.totalCompleted` | number | `48` | 총 완료 횟수 |

#### 4. 일별 기록 (`records.YYYY-MM-DD.*`)

각 날짜별로 묵상 기록을 저장.

| 키 | 값 타입 | 예시 | 설명 |
|---|---|---|---|
| `records.2026-04-22.completed` | boolean | `true` | 완료 여부 |
| `records.2026-04-22.prayed` | boolean | `true` | 기도했어요 버튼 눌렀는지 |
| `records.2026-04-22.underlines` | array | `[{verse: 16, range: [0, 30], color: "yellow"}]` | 밑줄 리스트 |
| `records.2026-04-22.emotions` | array | `["peaceful", "grateful"]` | 선택한 감정 (ID 배열) |
| `records.2026-04-22.memo` | string | `"오늘 말씀이 마음에 와닿는다..."` | 자유 메모 |
| `records.2026-04-22.completedAt` | ISO datetime | `"2026-04-22T07:23:15+09:00"` | 완료 시각 |
| `records.2026-04-22.progressStep` | number (0-4) | `3` | 어디까지 진행했는지 (이어하기) |

---

## 🎨 감정 ID 정의

```javascript
const EMOTIONS = {
  // 🟠 평온/감사 계열
  peaceful:  { label: "마음이 편안해졌어요", color: "#F4A261", category: "calm" },
  grateful:  { label: "감사함을 느껴요",     color: "#F4A261", category: "calm" },
  comforted: { label: "위로를 받았어요",     color: "#F4A261", category: "calm" },
  
  // 🟢 깨달음/결심 계열
  insight:      { label: "깨달음을 얻었어요", color: "#2A9D8F", category: "growth" },
  resolved:     { label: "결심이 생겼어요",   color: "#2A9D8F", category: "growth" },
  strengthened: { label: "의지가 커졌어요",   color: "#2A9D8F", category: "growth" },
  
  // 🟣 돌아봄/흔들림 계열
  reflective: { label: "나를 돌아보게 돼요", color: "#9B7EBD", category: "reflect" },
  curious:    { label: "궁금증이 생겨요",   color: "#9B7EBD", category: "reflect" },
  shaken:     { label: "마음이 흔들려요",   color: "#9B7EBD", category: "reflect" }
};
```

---

## 📝 밑줄 구조 상세

```javascript
{
  id: "uuid-v4",              // 고유 ID (삭제/수정용)
  verse: 16,                  // 절 번호
  range: {
    start: 10,                // 시작 문자 인덱스
    end: 45                   // 끝 문자 인덱스
  },
  text: "어머니의 하나님이 나의 하나님이 되시리니",  // 스냅샷 (원본이 변해도 보존)
  color: "yellow",            // yellow | pink | blue (향후)
  note: "",                   // 밑줄에 달린 개인 메모 (선택)
  createdAt: "2026-04-22T07:15:30+09:00"
}
```

---

## 🔄 연속일 계산 로직

```javascript
function updateStreak() {
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = getYesterday();
  const lastDate = localStorage.getItem('streak.lastDate');
  
  if (lastDate === today) {
    // 이미 오늘 완료 → 변경 없음
    return;
  }
  
  let current = parseInt(localStorage.getItem('streak.current') || '0');
  
  if (lastDate === yesterday) {
    // 어제도 했음 → +1
    current += 1;
  } else {
    // 끊김 → 1로 리셋
    current = 1;
  }
  
  localStorage.setItem('streak.current', current);
  localStorage.setItem('streak.lastDate', today);
  
  // 최장 연속일 업데이트
  const longest = parseInt(localStorage.getItem('streak.longest') || '0');
  if (current > longest) {
    localStorage.setItem('streak.longest', current);
  }
  
  // 총 완료 횟수
  const total = parseInt(localStorage.getItem('streak.totalCompleted') || '0');
  localStorage.setItem('streak.totalCompleted', total + 1);
}
```

---

## 📤 데이터 내보내기 (JSON Export)

설정 > 데이터 내보내기에서 사용.

```javascript
function exportAllData() {
  const data = {
    exportedAt: new Date().toISOString(),
    version: "1.0",
    user: { /* user.* */ },
    settings: { /* settings.* */ },
    streak: { /* streak.* */ },
    records: { /* 모든 records.* */ }
  };
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `jumanna-backup-${today}.json`;
  a.click();
}
```

---

## 🧹 데이터 초기화

사용자가 "데이터 초기화"를 누르면:

1. 확인 모달 두 번 (실수 방지)
2. `localStorage.clear()` 실행
3. 홈으로 리다이렉트 (온보딩부터 다시)

---

## 💡 용량 관리

localStorage 한계: 일반적으로 **5~10MB**

### 예상 사용량

| 데이터 | 크기 (1건) | 1년 누적 (365일) |
|---|---|---|
| records (밑줄+메모 포함) | ~2KB | ~730KB |
| settings | ~500B | 고정 |
| streak | ~200B | 고정 |

→ **1년 사용해도 1MB 이하**, 충분히 안전.

### 만약 한계 도달 시

- 1년 이상 지난 기록은 **IndexedDB**로 이관 (추후)
- 또는 서버 연동 옵션 제공 (Supabase 등)

---

## 🔒 프라이버시

- **서버에 전송되는 개인 정보 없음** (localStorage만 사용)
- 기기가 바뀌면 기록이 사라짐 (내보내기 기능으로 백업)
- 브라우저 쿠키/캐시 삭제 시 데이터 손실 가능 → 사용자에게 안내

---

## 📊 데이터 마이그레이션 (버전 관리)

향후 스키마 변경 시:

```javascript
const CURRENT_VERSION = 2;

function migrate() {
  const currentVersion = parseInt(localStorage.getItem('schema.version') || '1');
  
  if (currentVersion < 2) {
    // v1 → v2 마이그레이션 로직
    migrateV1toV2();
  }
  
  localStorage.setItem('schema.version', CURRENT_VERSION);
}
```
