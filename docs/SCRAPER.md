# 🕷️ 주만나 크롤러 설계

오륜교회 주만나 QT 페이지에서 매일의 성경 본문을 자동으로 가져오는 로직입니다.

---

## 🎯 대상 URL

- **메인**: https://oryun.org/life/?menu=248
- **특성**: 매일 새로운 QT가 업데이트됨 (평일/주말 무관)

---

## 📋 스크래핑할 데이터

실제 페이지에서 추출 가능한 정보 (2026년 4월 22일 검증 완료):

| 필드 | 예시 값 | 추출 방법 |
|---|---|---|
| `date_label` | `04.22수요일` | `<dt>` 또는 특정 셀렉터 |
| `title` | `회복으로 나아가라` | h1 또는 제목 요소 |
| `scripture_ref` | `룻기 1:15-22` | 제목 바로 옆 |
| `subtitle` | `나오미와 함께 가기로 결심한 룻` | 본문 위 소제목 |
| `verses_korean` | 15절~22절 한글 본문 배열 | `<li>` 또는 개별 절 요소 |
| `verses_english` | 동일 구절 영어 본문 | 하단 영문 섹션 |
| `questions` | "오늘의 만나" 질문들 | 질문 영역 |

---

## 🧰 기술 스택

| 구분 | 라이브러리 |
|---|---|
| HTTP 요청 | `requests` |
| HTML 파싱 | `BeautifulSoup4` |
| 인코딩 | `utf-8` |
| 언어 | Python 3.9+ |

---

## 📂 파일 구조

```
/scripts/
├── fetch_qt.py          # 메인 스크래퍼
├── parse_helpers.py     # 파싱 유틸리티
├── validate.py          # 데이터 검증
└── save_json.py         # JSON 저장

/data/
├── qt/
│   ├── 2026-04-22.json  # 일별 원본 데이터
│   ├── 2026-04-21.json
│   └── ...
└── ai/
    ├── 2026-04-22.json  # AI 생성 묵상
    └── ...
```

---

## 🔄 스크래핑 플로우

```
[1] HTTP GET 요청
    ↓
[2] HTML 파싱 (BeautifulSoup)
    ↓
[3] 주요 섹션 추출
    - 제목 영역
    - 본문 영역 (한글/영어)
    - 질문 영역
    ↓
[4] 데이터 정제
    - 공백 정리
    - 절 번호와 본문 분리
    - 이스케이프 문자 처리
    ↓
[5] 검증
    - 필수 필드 존재 확인
    - 날짜가 오늘인지 확인
    - 구절 개수 체크
    ↓
[6] JSON 저장
    /data/qt/YYYY-MM-DD.json
    ↓
[7] 성공 시 → AI 생성 스크립트 트리거
    실패 시 → 알림 발송 (Slack/Email)
```

---

## 💾 저장 포맷 (원본 데이터)

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
      "text_kr": "나오미가 또 이르되 보라 네 동서는 그의 백성과 그의 신들에게로 돌아가나니 너도 너의 동서를 따라 돌아가라 하니",
      "text_en": "\"Look,\" said Naomi, \"your sister-in-law is going back to her people and her gods. Go back with her.\""
    },
    {
      "number": 16,
      "text_kr": "룻이 이르되 내게 어머니를 떠나며 어머니를 따르지 말고 돌아가라 강권하지 마옵소서...",
      "text_en": "But Ruth replied, \"Don't urge me to leave you or to turn back from you..."
    }
  ],
  
  "oryun_questions": [
    "하나님께 속하기 위해 어떤 노력을 할 수 있습니까?",
    "내 삶에서 하나님께 맡기고 따라가야 할 영역은 무엇입니까?"
  ],
  
  "source_url": "https://oryun.org/life/?menu=248",
  "fetched_at": "2026-04-22T05:00:00+09:00"
}
```

---

## ⏰ 실행 스케줄 (GitHub Actions)

```yaml
# .github/workflows/daily_qt.yml
name: Daily QT Fetcher

on:
  schedule:
    # 매일 새벽 5시 (KST) = UTC 20:00 (전날)
    - cron: '0 20 * * *'
  workflow_dispatch:  # 수동 실행 가능

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install requests beautifulsoup4 openai
      
      - name: Fetch today's QT
        run: python scripts/fetch_qt.py
      
      - name: Generate AI meditation
        run: python scripts/generate_ai.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Commit updated data
        run: |
          git config user.name "QT Bot"
          git config user.email "bot@jumanna.app"
          git add data/
          git commit -m "feat: update QT for $(date +%Y-%m-%d)" || exit 0
          git push
```

---

## 🧩 핵심 코드 스켈레톤

### fetch_qt.py

```python
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
from pathlib import Path

URL = "https://oryun.org/life/?menu=248"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_page():
    """오륜교회 주만나 페이지 HTML 가져오기"""
    res = requests.get(URL, headers=HEADERS, timeout=30)
    res.raise_for_status()
    res.encoding = 'utf-8'
    return res.text

def parse_qt(html):
    """HTML에서 QT 데이터 추출"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 날짜 레이블 (예: "04.22수요일")
    date_elem = soup.find('dt', string=re.compile(r'\d{2}\.\d{2}'))
    date_label = date_elem.text.strip() if date_elem else None
    
    # 제목 & 구절 범위 (예: "회복으로 나아가라 룻기 1:15-22")
    title_line = date_elem.find_next('dd').text.strip()
    title, scripture_ref = split_title_and_ref(title_line)
    
    # 부제 (등장인물/주제 한 줄)
    subtitle = extract_subtitle(soup)
    
    # 구절 리스트
    verses = extract_verses(soup)
    
    # 오륜교회 제공 질문들
    questions = extract_questions(soup)
    
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "date_label": date_label,
        "title": title,
        "subtitle": subtitle,
        "scripture_ref": scripture_ref,
        "book_name": extract_book_name(scripture_ref),
        "chapter": extract_chapter(scripture_ref),
        "verses_start": extract_verse_start(scripture_ref),
        "verses_end": extract_verse_end(scripture_ref),
        "verses": verses,
        "oryun_questions": questions,
        "source_url": URL,
        "fetched_at": datetime.now().isoformat()
    }

def split_title_and_ref(line):
    """'회복으로 나아가라 룻기 1:15-22' → ('회복으로 나아가라', '룻기 1:15-22')"""
    # 책 이름 + 장:절 패턴 찾기
    pattern = r'(.+?)\s+([가-힣]+)\s+(\d+):(\d+)(?:-(\d+))?$'
    m = re.match(pattern, line.strip())
    if m:
        title = m.group(1).strip()
        ref = f"{m.group(2)} {m.group(3)}:{m.group(4)}"
        if m.group(5):
            ref += f"-{m.group(5)}"
        return title, ref
    return line, ""

def extract_verses(soup):
    """절 번호와 본문 파싱"""
    verses = []
    # li 요소에서 *숫자* 형태로 구분된 구절 추출
    items = soup.find_all('li')
    for item in items:
        text = item.text.strip()
        m = re.match(r'(\d+)\s+(.+)', text)
        if m:
            verses.append({
                "number": int(m.group(1)),
                "text_kr": m.group(2).strip(),
                "text_en": ""  # 영문은 별도 파싱
            })
    return verses

def save_json(data):
    """JSON 파일로 저장"""
    date = data['date']
    path = Path(f"data/qt/{date}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"✅ Saved: {path}")

if __name__ == "__main__":
    html = fetch_page()
    data = parse_qt(html)
    save_json(data)
```

---

## 🛡️ 에러 처리

### 일반적인 실패 시나리오

| 상황 | 처리 |
|---|---|
| 페이지 접속 실패 | 3회 재시도 (exponential backoff) |
| HTML 구조 변경 | 관리자 알림 + 어제 데이터 fallback |
| 날짜 불일치 (오늘 날짜 아님) | 경고 로그, 그래도 저장 |
| 구절 파싱 실패 | 부분 데이터라도 저장 + 알림 |
| AI 생성 실패 | 다음 스케줄에서 재시도 |

### 로깅

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/scraper.log'),
        logging.StreamHandler()
    ]
)
```

---

## 🧪 로컬 테스트

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 수동 실행
python scripts/fetch_qt.py

# 3. 결과 확인
cat data/qt/$(date +%Y-%m-%d).json | jq

# 4. AI 생성까지 테스트
python scripts/generate_ai.py
```

---

## 📌 주의사항

### robots.txt 준수

- 오륜교회 사이트의 `robots.txt` 확인 필요
- 크롤링 빈도: **하루 1회**만 (과도한 요청 금지)
- User-Agent 명확히 표기

### 법적/윤리적 고려

- 개인 QT용으로만 사용
- 원본 URL 항상 보존 (`source_url`)
- 재배포 시 출처 명시 필수
- 상업적 이용 금지

### HTML 구조 변경 대응

오륜교회 사이트 리뉴얼 시 파싱 로직 수정 필요:
- 주요 셀렉터는 `parse_helpers.py`에 상수로 분리
- 구조 변경 감지 시 관리자에게 알림
- 폴백: 어제 데이터 재사용

---

## 🔄 향후 개선 아이디어

- [ ] 월별 목차 페이지 크롤링 (미리보기 제공)
- [ ] 영문 본문 별도 파싱 추가
- [ ] 음성 파일(MP3) 링크 추출
- [ ] 변경 감지: 같은 날짜 페이지가 수정되었는지 체크
- [ ] Docker 컨테이너화
