# 🤖 AI 프롬프트 운영 노트

매일의 주만나 본문을 AI로 묵상 콘텐츠로 바꾸는 파이프라인의 **운영 메모**입니다.
프롬프트 전문·출력 스키마는 코드가 단일 기준이므로 여기 중복해 두지 않습니다.

## 📌 단일 기준 (Source of Truth)

| 항목 | 위치 |
|---|---|
| System / User / 2-pass 정제 프롬프트 (실서비스, Python) | [`scripts/generate_ai.py`](../scripts/generate_ai.py) — `SYSTEM_PROMPT`, `build_user_prompt()`, `build_refine_prompt()` |
| 동일 프롬프트의 JS 미러 (Cloudflare Worker 경로) | [`workers/src/prompts.js`](../workers/src/prompts.js) |
| 출력 JSON 스키마 | [`docs/DATA_SCHEMA.md`](DATA_SCHEMA.md) — `/data/ai/YYYY-MM-DD.json` |
| 입력(QT 크롤링) 데이터 스키마 | [`docs/DATA_SCHEMA.md`](DATA_SCHEMA.md) — `/data/qt/YYYY-MM-DD.json` |
| 생성 후 검증 | `scripts/generate_ai.py`의 `validate()` / `workers/src/validate.js`의 `validateAi()` |

생성 흐름: `fetch_qt.py` → `generate_ai.py`(1차 전체 생성 temperature 0.7 → 2차 `application`만 정제 temperature 0.3) → `data/ai/`. 자세한 건 [`scripts/README.md`](../scripts/README.md), [`docs/HANDOFF.md`](HANDOFF.md) 참고.

---

## 💰 비용

- 모델: `gpt-4o-mini` (Worker 경로는 `claude-haiku-4-5`)
- 1회 호출 합계 대략 입력 4~7k · 출력 0.7~1k 토큰
- 1일 약 **$0.001 (1~2원)**, 연간 **약 500원** — 개인 프로젝트로 충분
- 실제 비용은 각 `data/ai/{date}.json`의 `_cost` 필드에 기록됨

## ⚙️ 모델 업그레이드 트리거

`gpt-4o-mini`로 운영하다가 아래가 잦으면 `gpt-4o`(또는 더 큰 모델) 검토:

- [ ] 장면 요약이 너무 뻔함
- [ ] 등장인물 설명이 사전적이고 깊이 없음
- [ ] 기도문이 공장에서 찍어낸 듯함
- [ ] 적용 포인트가 본문과 연결 안 됨
- [ ] 신학적으로 명백히 잘못된 해석 발생

## 🔄 실패/재생성 전략

1. 1차 생성 → `validate()` 경고 확인 (경고는 비차단 — 로그만)
2. API 호출 실패 시 GitHub Actions가 mock 모드(`--mock`)로 폴백 — 샘플 묵상이라도 빈 화면은 피함
3. 2차 정제 실패 시 1차 결과를 그대로 사용
4. 데이터 자체가 없는 날: 프론트엔드가 최근 3일치까지 자동 폴백 (`step-2-meditation.html`의 `loadWithFallback`)

---

## 📝 콘텐츠 가이드라인

### 신학적 균형
- 오륜교회는 **개신교 복음주의 노선**. 이 노선에서 벗어나는 해석(성경무오 부정, 다른 복음 등)은 피한다.
- 논쟁적 교리(예정론 vs 자유의지 등)는 중립적 언어 사용.
- 저자·연대 논쟁이 있는 책(히브리서·베드로후서·모세오경·이사야·욥기 등)은 "전해집니다", "여러 견해가 있습니다" 같은 완충 표현 — 단정 금지. (프롬프트 #3 `book_overview`에 명시됨)

### 본문 왜곡 금지
- AI가 임의로 성경 구절을 바꾸거나 축약하지 않는다. 원본 구절은 항상 `data/qt/`에 별도 보존.
- AI 해설은 **보조 설명**일 뿐 성경 자체가 아님.

### 표현 규칙 (프롬프트에 반영됨)
- 존댓말, 짧은 문장, 신학 용어는 풀어 설명, 훈계 톤 금지.
- 적용문은 "저는 오늘, ~" 등 1인칭 자기 낮춤 ("나" → "저"), 세 항목은 서로 다른 시작.
- 위계적·시혜적 표현("~에게 은혜를 베풀겠습니다", "이웃을 가르치겠습니다") 금지.
- 금지어: `여러분`, `~해야만`, `반드시 해야`.

### 저작권
- 생성된 묵상은 **개인용**. 무단 배포·상업적 이용 금지.
- 오륜교회 원본 링크(`source_url`)는 항상 데이터에 포함.
