# 주만나 QT Daily Worker

Cloudflare Workers + Cron Triggers 로 매일 KST 05:00 에 오륜교회 주만나 페이지를 크롤링하고 OpenAI 묵상을 생성해 GitHub repo 의 `data/qt/*.json`, `data/ai/*.json` 에 자동 커밋합니다.

기존 GitHub Actions cron 의 지연·누락 문제를 피하기 위한 메인 자동화이고, GitHub Actions 백업 워크플로(`daily_qt_backup.yml`)가 KST 06:00 에 보조로 돕니다.

---

## 1. 사전 준비

### 1-1. Cloudflare 계정
- [https://dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up) 에서 계정 생성 (이메일: `ioapdlvmff@gmail.com`)
- Workers & Pages → Get Started 클릭
- 무료 플랜 활성화 (결제 카드 등록 없이 시작 가능)

### 1-2. Discord Webhook (실패 알림 — **선택, 나중에 추가 가능**)
알림은 지금 건너뛰셔도 Worker는 정상 동작합니다. 나중에 추가하고 싶을 때 다음을 수행하세요:

1. 디스코드에서 알림 받을 서버 만들거나 기존 서버 선택
2. 알림용 채널 하나 생성 (예: `#qt-bot`)
3. 채널 우측 ⚙️ 톱니바퀴 → **Integrations → Webhooks → New Webhook**
4. 이름 정하고 (예: "QT Bot") **Copy Webhook URL** 클릭
5. 시크릿 한 개만 추가하면 즉시 활성화: `wrangler secret put DISCORD_WEBHOOK_URL`

### 1-3. GitHub Fine-grained PAT
- GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
- 항목:
  - Token name: `jumanna-qt-worker`
  - Expiration: **1년**
  - Resource owner: 본인 계정
  - Repository access: **Only select repositories** → `yeseong000/QT-full` 선택
  - Permissions → Repository permissions → **Contents: Read and write**
- 생성 후 토큰 문자열을 즉시 복사 (한 번만 표시됨)
- 캘린더에 1년 뒤 갱신 리마인더 등록 권장

---

## 2. 로컬 개발 (선택)

```bash
cd workers
npm install
cp .dev.vars.example .dev.vars   # 그리고 실제 시크릿 채우기

# 로컬 개발 서버
npx wrangler dev

# 다른 터미널에서 수동 실행
curl http://localhost:8787/run
```

`/run` 호출 시 실제로 GitHub repo 에 커밋이 들어갑니다. 테스트용으로 실 repo 를 오염시키지 않으려면 `.dev.vars` 의 `GITHUB_REPO` 를 별도 fork로 설정하세요.

---

## 3. 배포

### 3-1. 시크릿 등록

```bash
cd workers
npx wrangler login   # 처음 한 번 (브라우저 인증)

npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put GITHUB_REPO       # yeseong000/QT-full
npx wrangler secret put GITHUB_BRANCH     # main

# 디스코드 알림은 선택 — 나중에 추가하고 싶을 때 이 줄만 실행
# npx wrangler secret put DISCORD_WEBHOOK_URL
```

각 명령 실행 후 값을 입력하라는 프롬프트가 뜨면 위 값을 붙여넣고 Enter.

디스코드 시크릿이 없으면 Worker 로그에 "알림 환경변수가 없어 디스코드 발송 생략" 이라는 줄이 찍히고 정상적으로 다음 단계가 진행됩니다.

### 3-2. 배포

```bash
npx wrangler deploy
```

배포 결과 메시지에 표시되는 Worker URL (예: `https://jumanna-qt-daily.<your-subdomain>.workers.dev`) 을 메모해두세요.

---

## 4. 검증 (배포 직후 1회)

### 수동 트리거
```bash
curl https://jumanna-qt-daily.<your-subdomain>.workers.dev/run
```

또는 Cloudflare Dashboard → Workers → `jumanna-qt-daily` → Triggers → "Send Cron Trigger" 버튼 클릭.

### 성공 신호 체크리스트
- [ ] curl 응답 `OK` (200)
- [ ] GitHub repo `commits` 에 `chore(data): 자동 크롤링 · YYYY-MM-DD QT (Worker)` 와 `... AI 묵상 (Worker)` 두 개 커밋
- [ ] Vercel Dashboard → Deployments 의 최신 deploy `Ready`
- [ ] 사이트에서 오늘 묵상이 정상 노출

### 디스코드 알림을 나중에 추가했다면
시크릿 중 `OPENAI_API_KEY` 를 일부러 잘못된 값으로 바꿔 한 번 실행해보세요. 디스코드 채널에 "❌ 주만나 QT 자동 생성 실패" 메시지가 도착하면 알림 경로가 정상입니다. 검증 후 시크릿을 원래대로 되돌리세요.

---

## 5. 기존 GitHub Actions 정리 (Worker 검증 후)

배포 + 검증이 끝나면, **기존 `.github/workflows/daily_qt.yml` 을 삭제**하세요. 그렇지 않으면 매일 KST 05:00 에 GitHub Actions와 Worker가 동시에 실행되어 OpenAI 비용이 두 배로 나갑니다.

```bash
git rm .github/workflows/daily_qt.yml
git commit -m "chore(workflow): 메인 cron 제거 — Cloudflare Worker로 이전"
git push
```

새 백업 워크플로 `.github/workflows/daily_qt_backup.yml` 은 KST 06:00 에 실행되고, Worker가 이미 파일을 만들었으면 즉시 skip 합니다. defense in depth 용도로 그대로 두세요.

---

## 6. 운영 모니터링

### 매일 확인 위치
- Cloudflare Dashboard → Workers → `jumanna-qt-daily` → **Cron Events** 탭: 매일 05:00 KST 부근의 실행 기록과 status (`success` / `error`)
- Cloudflare Dashboard → Workers → `jumanna-qt-daily` → **Logs** 탭: 실시간 로그
- GitHub repo의 `data/qt/`, `data/ai/` 폴더에 오늘 날짜 파일이 매일 새로 들어왔는지 확인
- (디스코드 활성화 시) 디스코드 채널: 실패 알림

### 7일 안정화 관찰
배포 후 7일간 매일 새 커밋이 KST 05:01 ~ 05:02 사이에 들어오는지 GitHub commits 페이지에서 확인. 7일 연속 정상이면 운영 안정화 완료입니다.

---

## 7. 트러블슈팅

| 증상 | 원인 후보 | 조치 |
|---|---|---|
| Worker 가 timeout | OpenAI 응답 지연 또는 무료 플랜 CPU 한도 | Cloudflare Dashboard → Plan → Workers Paid ($5/월) 업그레이드 |
| GitHub 커밋 실패 401 | PAT 만료 또는 권한 오류 | 새 PAT 발급 → `wrangler secret put GITHUB_TOKEN` 으로 갱신 |
| GitHub 커밋 실패 404 | `GITHUB_REPO` 또는 `GITHUB_BRANCH` 오타 | 시크릿 재등록 |
| 이메일 미도착 | Resend 도메인 정책 | 가입한 본인 메일이 `NOTIFY_EMAIL_TO` 와 일치하는지 확인 |
| 페이지 파싱 실패 | 오륜교회 HTML 구조 변경 | `src/fetch_qt.js` 의 셀렉터/정규식 수정. Python `scripts/fetch_qt.py` 도 동일하게 수정 |

---

## 8. 파일 구조

```
workers/
├── wrangler.toml              # Worker 설정 + Cron 스케줄
├── package.json               # cheerio, wrangler 의존성
├── .gitignore
├── .dev.vars.example          # 로컬 개발용 환경변수 템플릿
├── README.md                  # 이 파일
└── src/
    ├── index.js               # scheduled() / fetch() 진입점
    ├── fetch_qt.js            # 오륜교회 크롤링 (Python 1:1 포팅)
    ├── generate_ai.js         # OpenAI 2-pass 호출
    ├── prompts.js             # SYSTEM_PROMPT, REFINE_SYSTEM_PROMPT 등
    ├── validate.js            # AI 출력 검증 (5/3/3/8~14 + 금지어)
    ├── github.js              # GitHub Contents API 래퍼
    ├── notify.js              # Resend 이메일 발송
    └── util.js                # 공통 유틸
```

원본 Python 스크립트 (`scripts/fetch_qt.py`, `scripts/generate_ai.py`) 는 백업 GitHub Actions 워크플로가 계속 사용하므로 삭제하지 않습니다.
