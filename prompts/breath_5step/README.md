# 5단 호흡 묵상 GPT 프롬프트

주만나 AI 큐티의 묵상 섹션(5단 호흡 카드)을 생성하는 GPT 프롬프트입니다.

## 디렉토리 구조

```
prompts/breath_5step/
├── parts/                          ← 룰 파일들 (수정은 여기서)
│   ├── 01_role_and_tone.md         역할·톤·금지 어휘
│   ├── 02_output_format.md         입출력 JSON 형식
│   ├── 03_rule_sentence.md         문장 룰 (명시화·시제·축약)
│   ├── 04_rule_scene.md            장면 룰 (인물·동적 묘사·본문 유형 분기)
│   ├── 05_rule_question.md         질문 룰 (열린 의문·비교 절제)
│   ├── 06_rule_context.md          디테일 룰 (본문 밀착·출처 표지·반복 구조)
│   ├── 07_rule_bridge.md           연결 룰 (3단계 호흡·주만나 정렬)
│   └── 08_alignment_check.md       자가 검증·모델 설정
├── _final_system.md                ← 자동 생성. GPT API 호출 시 사용
├── breath_5step_examples.json      ← fewshot 예시 5개
├── build.py                        ← 합본 빌드 스크립트
└── README.md                       ← 이 파일
```

## 사용 흐름

### 1. 룰 수정 (필요 시)

`parts/*.md` 중 해당 파일을 수정합니다.

### 2. 합본 빌드

```bash
cd prompts/breath_5step
python3 build.py
```

`_final_system.md`가 자동 갱신됩니다.

### 3. GPT API 호출 (Python 예시)

```python
from pathlib import Path
import json
from openai import OpenAI

client = OpenAI()
prompt_dir = Path("prompts/breath_5step")

# 시스템 프롬프트 로드
system_prompt = (prompt_dir / "_final_system.md").read_text(encoding="utf-8")

# fewshot 예시 로드
examples = json.loads((prompt_dir / "breath_5step_examples.json").read_text(encoding="utf-8"))

# fewshot을 messages로 변환
fewshot_messages = []
for ex in examples:
    fewshot_messages.append({"role": "user", "content": json.dumps(ex["input"], ensure_ascii=False)})
    fewshot_messages.append({"role": "assistant", "content": json.dumps(ex["output"], ensure_ascii=False)})

# 오늘의 입력 (크롤러 출력 기반)
today_input = {
    "본문_참조": "사무엘상 4:12-22",
    "본문_제목": "하나님의 영광이 떠날 때",
    "본문_내용": "...",
    "오륜_질문": ["...", "..."],
    "지식": None
}

# API 호출
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        *fewshot_messages,
        {"role": "user", "content": json.dumps(today_input, ensure_ascii=False)}
    ],
    temperature=0.7,
    response_format={"type": "json_object"},
    max_tokens=1500
)

result = json.loads(response.choices[0].message.content)
print(result["장면"])
```

## 주요 룰 요약

### 절대 룰 (어김 = 즉시 재작성)

- 어미는 ~이에요/~거예요로 통일 (~입니다 금지)
- 가상 인물 금지 (잠언 명제·시편 표제 없는 본문)
- KB 없으면 추측 금지 (본문 자체에서 확인되는 디테일만)
- 호칭 금지 ("여러분", "성도님")

### 핵심 룰 (장르별 분기)

| 본문 유형 | 장면 작성 방식 |
|----------|------------|
| 내러티브, 복음서 | 본문 인물 즉시 노출 + 내면 상태 |
| 서신서, 권면 | 발신자 + 청중 상황 묘사 |
| 시편 (표제 있음) | 표제 시인이 화자 |
| 잠언 (호칭 형식) | 본문 안 호칭 사용 |
| 잠언 (명제 형식), 전도서 | 본문 자체를 무대로 (인물 X) |

## GPT 설정 권장값

- 모델: `gpt-4o-mini`
- temperature: `0.7`
- response_format: `{ "type": "json_object" }`
- max_tokens: `1500`

## 향후 작업

- [ ] 가계도 기능 (별도 트랙)
- [ ] KB 데이터 확장 (룻기 외 다른 책)
- [ ] 시편 표제 분기 추가 검증
