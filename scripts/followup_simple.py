"""떠오르는 질문 — 단순 아키텍처 v3 (실험용, 운영 아님).

사용자 확정 설계: "질문은 싸게 잔뜩 만들어 거르고, 답변은 살아남은 9개에만 쓴다."

흐름 (딱 4단계):
    ① 질문 뽑기   — 서로 다른 소재 16개 × 질문 1개(대등한 후보 16개), 답변 없이. 싸다.
    ② 거르기      — "독자가 이미 아는 것"과 겹치면 탈락. 출처 3군데:
                     [체1] 지난 질문(과거 날짜)        … 코드(글자)
                     [체2] 오늘 질문끼리              … 코드(글자) + mini(뜻)
                     [체3] 이미 읽은 본문 구절·5단 묵상 … mini(뜻)  ← 다윗 나이(5:4)류 여기서 탈락
    ③ 좋은 9개    — 답 겹침·카테고리 다양하게 9개 선택 후 메인3·꼬리6으로 짝지음.
    ④ 답변 쓰기   — 확정 9개에만 4o로 1회(fp.write_answers=검증·재시도 내장).

코드가 하는 것: 명백한 글자 중복(체1, 체2 표면). mini가 하는 것: 뜻을 읽어야 아는 것
(체2의 '메인에 꼬리 포함', 체3의 본문·5단 재진술). 비싼 답변(4o)은 질문이 다 깨끗해진
뒤 마지막에 딱 한 번 → 교체 때문에 헛돌아도 버려지는 건 값싼 질문(mini)뿐.
"""
import datetime
import re
from difflib import SequenceMatcher
from collections import Counter, defaultdict

import followup_pool as fp
import openbible_xref

PARTS_DIR = fp.PARTS_DIR

Q_MODEL = "gpt-4o"           # 질문 후보 생성 (구체·구별되는 질문 위해 4o. 판정/교체는 mini 유지)
JUDGE_MODEL = "gpt-4o-mini"  # 체3(+체2 포함) 알맹이/재진술 판정
QFIX_MODEL = "gpt-4o-mini"   # 걸린 질문 교체
# 답변은 fp.write_answers가 gpt-4o로 쓴다(검증+재시도 내장).

# 후보는 '서로 다른 소재 16개 × 질문 1개'. 예전엔 '메인 6개 × (자기+꼬리2) = 18개'였는데,
# 꼬리는 스키마상 메인의 후속 질문이라 같은 소재인 게 정상 → 서로 다른 지식의 천장이 6개로
# 묶여버렸다(9개 요구 > 천장 6 → 3개는 필연적으로 중복). 게다가 _assemble_diverse가 그 묶음
# 구조를 어차피 해체하고 다시 짝지으므로, 꼬리를 메인에 매달아 뽑을 이유 자체가 없었다.
# (2026-07-17 실측: 7/16 운영분은 6묶음 중 5묶음이 통째로 1덩이로 뭉쳐 천장 6 → distinct 6/9)
#
# 22인 이유 — '판정에서 버려질 몫'까지 계산에 넣는다.
# 판정 통과율 실측: 7/13·7/14는 15/16(94%)인데 7/15는 9/16(56%)였다. 56%는 이상한 값이
# 아니다 — Self-Instruct도 생성물의 약 절반을 버린다(ROUGE-L 0.7 컷). 문제는 16이라
# 여유가 없었던 것: 16 × 0.56 = 9.0, 즉 딱 9개만 남아 창고가 텅 비었다. 그래서 걸린 질문을
# 갈아끼울 재고가 없어 모델에게 새로 쓰게 했고, 그 질문엔 출처 기록이 없어 절 배치 보호를
# 못 받았다(7/15: 9개 중 7개가 그렇게 교체 → 그날 유일한 겹침이 거기서 났다).
# 22면 나쁜 날(56%)에도 22 × 0.56 ≈ 12개가 통과해 여유분 3개가 남는다.
# 계층 구조가 없어 후보를 늘려도 싸다(출력 +약 270토큰 ≈ 4원/일). 대신 교체 GPT 호출이
# 사라지므로 7/15 같은 날은 오히려 싸진다.
NUM_CANDIDATES = 22
SELECT_MAINS = 3             # 최종 선택 묶음 수 (3묶음 = 9개)

_ZERO_COST = fp._ZERO_COST
_ROLE_IDS = fp._ROLE_IDS
_GOOD = "좋음"
_JUDGE_VERDICTS = [_GOOD, "본문재진술", "5단재진술", "메인에포함", "얕음"]


# ===== 프롬프트 =====
_Q_WRAPPER = """# 떠오르는 질문 — 질문 후보 생성기 (질문만, 답변 없음)

오늘 본문·`지식`·`관주_연결`·`최근_본문`에 근거해 **질문 후보를 최대 {N}개**까지 만든다. **답변은 만들지 않는다** — 질문 문장만. 후보는 전부 대등하다(메인·꼬리를 나누지 마라 — 화면 배치는 코드가 알아서 한다).

## 여기서 만들지 않는 것
**관주형·전날형은 별도 생성기가 맡는다.** 여기서는 오늘 본문(`본문_내용`)과 `지식`만으로 만들어라.

## 순서가 중요하다 — 관찰이 먼저, 질문은 그다음

**질문부터 쓰지 마라.** 먼저 `observations`에 **절을 하나씩 훑으며 '이상한 것'**을 적는다. 그다음 관찰 하나당 질문 하나를 만든다.

**관찰이란 '어? 왜 이렇게 적혀 있지?' 하는 지점이다.** 인물의 속셈을 짐작하는 게 아니라, 본문에 실제로 적힌 것 중 눈에 걸리는 것이다.
- ✓ "2절 — 찾아온 사람에게 하필 **출신 지파**를 먼저 물었다"
- ✓ "5절 — 입 맞추기 전에 **절하려는 걸 붙들어 막았다**"
- ✓ "3절 — '왕께서 재판할 사람을 세우지 아니하셨다'는 **압살롬의 주장이다. 사실인지 확인이 필요하다**"
- ✓ "6절 — 서술자가 여기서 딱 한 번 '**훔치니라**'라고 판정을 내린다"
- ✗ "압살롬이 민심을 얻으려 했다" (관찰이 아니라 해석 — 이런 건 적지 마라)

**관찰은 `kind`로 나눈다.** `본문`(오늘 절) · `관주`(그 절의 `관주_연결` 중 눈에 띄는 구절 — `ref`에 구절 참조) · `전날`(`최근_본문`과 이어지는 대목) · `KB`(`지식` 재료 — `ref`에 재료 번호).
**절마다 `관주_연결`을 반드시 훑어라.** 오늘 본문이 얇은 날일수록 여기에 재료가 있다.

## 질문 개수는 관찰이 정한다
**관찰 하나당 질문 하나.** 관찰이 8개면 질문도 8개다. **개수를 채우려고 같은 관찰에서 질문을 두 개 뽑지 마라.**
오늘 본문이 얇아(절이 적거나 장면이 하나뿐) 본문 관찰이 적게 나오면, **관주 관찰을 3개까지 늘려** 채운다. 억지로 본문을 쥐어짜지 마라.

**개수보다 '서로 다름'이 먼저다.** 서로 다른 질문거리가 {N}개보다 적으면 **거기서 멈춰라 — 적게 내도 된다.** 같은 질문을 문장만 바꾸거나 그대로 복사해서 개수를 채우는 건 **가장 나쁜 결과**다(코드가 잡아내 통째로 버린다). 재료가 얇은 날엔 12개만 나와도 정상이다.

## 가장 중요 — 질문 하나당 서로 다른 '자리' 하나
질문마다 그 질문이 걸린 자리를 함께 밝힌다. **코드가 원자료와 대조해 검사하고, 틀리면 그 질문은 버려진다.** 자리는 **세 종류**다.

**① 본문형** (`anchor_type: "본문"`) — 오늘 본문 절을 파고드는 질문
- `verse` 절 번호(정수) · `anchor` **그 절에서 글자 그대로 복사한 2~15자 표현**(요약·바꿔쓰기 금지)
  - ✓ 6절 "…벧르홉 아람 사람과 소바 아람 사람의 보병…" → `verse: 6, anchor: "벧르홉 아람 사람"`
  - ✗ `anchor: "아람 용병 고용"` (본문에 없는 네 요약 — 탈락)

**② 관주형** (`anchor_type: "관주"`) — 관주 구절이 알려주는 '오늘 본문의 숨은 배경'을 여는 질문. **그냥 "다른 성경과 연결되나요?"가 아니다.** 오늘 본문에 나오지만 초신자가 모를 ⓐ **낯선 인물의 정체** · ⓑ **본문이 인용하는 옛 사건** · ⓒ **그 행동·판결의 근거가 된 율법·관습**을 그 관주 구절로 밝힌다.
- `verse` 오늘 본문의 절 번호 · `anchor` **`관주_연결`에 실제로 적힌 구절 참조를 그대로** (예: `"삼하 23:39"`). 목록에 없는 구절을 지어내면 탈락한다.
- 질문은 그 배경을 **콕 집어** 연다. 답을 흘리는 '누가·어느'를 쓰지 말고 '**어떻게·어떤·원래 어떤 사람/사건**'으로.
  - ✗ **뭉개기 절대 금지** (소재가 오늘 것 그대로라 다른 질문과 답이 겹친다): "우리아 사건은 **다른 성경 구절과 어떻게 연결되나요?**" / "**비슷한 이름의** 다른 인물은?" / "**다른 성경에도** 비슷한 게 있나요?"
  - ✓ **배경을 물어 소재가 갈라진다:** "다윗이 죽음으로 내몬 '**헷 사람 우리아**'는 **원래 어떤 사람**이었나요?" (→ 삼하 23:39, 다윗의 37용사) / "다윗이 양을 '**네 배로 갚으라**'(12:6) 한 건 **어떤 근거**였나요?" (→ 출 22:1, 도둑 배상법)
- 재해석·신학 논쟁 성격의 연결(회개 신학·남 판단 등)은 이 각도가 아니다. **카테고리는 반드시 `관주`**(옛 이름 '연결 질문'은 쓰지 마라). **`관주_연결`이 있는 날엔 이 배경지식형을 1~2개 꼭** 넣되, 절반을 넘기지 마라(성경 상식 퀴즈가 아니다).

**③ KB형** (`anchor_type: "KB"`) — `지식`의 `인물`·`주의점`·`신학_핵심` 재료를 파고드는 질문
- `anchor` **그 재료에 붙은 번호를 그대로** (예: `"7:인물#2"`, `"7:주의점#5"`) · `verse`는 `0`으로 둔다
  - ✓ `지식`에 `"7:인물#2": {...아비아달...}`이 있으면 → `verse: 0, anchor_type: "KB", anchor: "7:인물#2"`
  - ✗ 없는 번호를 대거나(`7:주의점#99`) 번호 대신 내용을 요약해 적으면 탈락한다.
- **이 재료는 절 본문에 글자로 안 나오는 배경**(인물의 정체·당시 관습·해석 견해)이라, 본문형으로는 열 수 없는 각도다. **`인물`·`주의점` 재료가 있는 날엔 2~3개를 꼭 넣어라.**
- 재료에 없는 사실을 보태지 마라. 그 재료가 말하는 범위 안에서만 묻는다.

**세 종류는 전부 서로 다른 자리다.** 18절 "여호와 앞에 들어가 앉"(본문형)과 18절↔시편 8:4(관주형)와 `7:인물#2`(KB형)는 답이 완전히 달라 셋 다 쓸 수 있다.

**한 자리에 1개가 원칙이다.** 자리가 모자랄 때만 한 절에 2개까지 얹되, `anchor`가 서로 달라야 한다(예: 5절 "수염이 자라기까지" / 5절 "여리고").

한 자리에 몰면 문장을 아무리 다르게 써도 답은 같은 대목을 설명하게 된다. KB에 어원·지명 자료가 있으면 그 각도를 꼭 하나씩 넣는다(없으면 억지로 안 만든다).

## 두루뭉술 금지 — 본문의 '구체적 단어·행동'을 콕 집어라 (매우 중요)
"~의 **의미**는?" "~의 **영향**은?" "~의 **변화**는?" 같은 두루뭉술한 질문은 **답이 서로 겹치고 본문에 딱 붙지 않는다** — 절대 이런 걸로 채우지 마라. 대신 **본문에 실제 나온 구체적 단어·표현·행동·숫자·대비**를 하나 콕 집어 물어라. 본문은 짧아 보여도 파고들면 서로 다른 지점이 열 개 넘게 나온다.
- ✗ "다윗 통치의 의미는?" / "약속이 통치에 미친 영향은?" / "즉위가 이스라엘에 준 영향은?" (두루뭉술, 답 겹침)
- ✓ 본문에 나온 특정 단어를 집는다: "본문이 다윗을 왕의 '골육'이라 부른 건 무슨 뜻인가요?" / "여호와가 '목자'와 '주권자' 두 호칭을 함께 쓴 이유는?" / "장로들과 '언약'을 맺은 건 어떤 절차였나요?" / "왜 헤브론에서만 칠 년 반을 다스렸나요?" / "다윗이 기름 부음을 받은 게 이번이 몇 번째인가요?"
- 판단법: 질문을 보고 "본문의 **어느 단어·구절**에서 나온 건지" 짚을 수 있어야 한다. 못 짚으면 두루뭉술한 것이니 버려라.

## 카테고리는 '가이드'일 뿐
아래 공유 규칙의 카테고리 목록은 다양한 각도를 떠올리게 하는 가이드다. 그날 KB·본문이 뒷받침하지 않는 각도(어원 자료 없는 날의 원어 등)는 억지로 만들지 말고, 본문에서 직접 확인되는 관찰·디테일·인물·연결로 대체한다. 없는 원어 뜻·현대 지명·역사 추정으로 질문을 지어내지 않는다.

## 되묻기 금지 (독자는 이미 ⓐ오늘 본문 구절 ⓑ5단 묵상을 읽었다)
1. **지난 질문** — `같은_책_기존_STEP2_질문`과 소재·맥락이 겹치면 문장이 달라도 안 된다.
2. **이미 읽은 본문·5단** — 답이 오늘 본문 구절에 그대로 적혀 있거나(예: "다윗 나이 30세" — 5:4에 그대로), 5단이 이미 밝힌 사건·동기를 되묻는 것 금지.

단, 5단이 안 다룬 주변 배경을 여는 '왜'는 오히려 알맹이다(브에롯 왜 이주, 헬갓핫수림 유래, 적 머리 관습). 막는 건 '이미 읽은 걸 되묻기'이지 '왜'라는 단어가 아니다.

## 출력
`{"candidates": [ {"question","category","topic","verse","anchor","anchor_type"} ×최대 {N} ]}`
- `question` 눌러보고 싶은 짧은 제목형 한 문장 · `category` 각도 라벨 · `topic` 1~4단어 소재 라벨
- `verse` 절 번호(정수, KB형은 `0`) · `anchor_type` `"본문"`·`"관주"`·`"KB"` 중 하나
- `anchor` 본문형이면 그 절에서 복사한 2~15자, 관주형이면 `관주_연결`에 적힌 구절 참조, KB형이면 `지식`의 재료 번호(`7:인물#2`)
- **자리를 골고루 퍼뜨리고, `anchor`가 전부 서로 달라야 한다.**"""

_JUDGE_WRAPPER = """# 떠오르는 질문 — 알맹이/재진술 판정기

각 후보 질문이 '독자에게 새로운가'를 판정한다. 독자는 이 질문 앞에서 이미 ①오늘 본문 구절(`본문_내용`) ②5단 묵상(`이미_다룬_5단`, 본문 따라가기)을 읽었다. 답변을 상상해서, 그 답이 이미 어딘가에 있으면 알맹이가 없다.

각 질문마다 `verdict`를 정확히 하나로:
- **좋음** — 답이 본문 구절·5단·(꼬리면) 같은 가지 메인 어디에도 그대로 없고, 새 각도(어원·배경·인물·지명·연결·문화)를 연다.
- **본문재진술** — 답이 오늘 `본문_내용` 절에 이미 그대로 적혀 있다. 예: "다윗이 왕위에 오른 나이는?" → 5:4에 '삼십 세에 왕위에 올라'가 그대로 있음.
- **5단재진술** — 답이 `이미_다룬_5단`이 이미 밝힌 사건·동기의 되풀이다.
- **메인에포함** — (그 질문이 '꼬리'일 때만) 답이 `이_꼬리의_메인_질문`의 답 안에 이미 들어갈 내용이다. 예: 메인 "죽인 방식의 의미?"의 답에 "적 머리=승리"가 이미 들어가는데 꼬리가 그걸 또 물음.
- **얕음** — 재진술은 아니지만, 답을 알아도 본문 이해가 안 바뀌는 트리비아.

의심스러우면 '좋음'을 기본으로 주지 말고, 정말 답이 이미 있는지 본문·5단 문장과 대조해라. 너는 판정만 한다 — 고쳐 쓰지 않는다.

## 갈래별 예외 (중요)

각 후보에 `갈래`가 붙어 있다. `갈래`가 `관주`나 `전날`이면 **답이 오늘 본문 밖에 있다** — 오늘 본문·5단과 대조해 봐야 없는 게 당연하다.

- **`갈래: 관주`** — 답은 `근거`에 적힌 **다른 성경 구절**의 내용이다. 오늘 본문에 없다고 '얕음'을 주지 마라. 다른 성경 이야기를 여는 것이 이 질문의 목적이다.
  - ✓ 좋음 — "남의 밭에 불을 지른 일이 성경에 또 있나요?"(근거: 사사기 15:4-5 삼손) · "다말과 같은 이름을 가진 인물이 또 있나요?"(근거: 사무엘하 13:1)
  - '얕음'은 그 관주 구절이 오늘 본문과 **아무 상관이 없을 때만** 준다.
- **`갈래: 전날`** — 답은 **앞 며칠 본문**에 있다. 너에게는 앞 본문이 주어지지 않았으니, 오늘 5단과 소재가 겹쳐 보여도 '5단재진술'을 주지 마라.
- 두 갈래에 줄 수 있는 부정 판정은 사실상 **`본문재진술`(답이 오늘 본문 절에 그대로 적혀 있는 경우)** 하나다.

## 두 번째 임무 — '답이 겹치는 지식 묶음' 그룹핑 (매우 중요)
질문 문장이나 카테고리가 달라도 **답을 쓰면 사실상 같은 지식·맥락을 설명하게 되는 질문들**이 있다. 독자는 묶음당 1개만 있으면 그 지식을 얻는다 — 나머지는 같은 걸 반복하는 것이다.

**반드시 이 순서로 판단해라:**
1. 각 질문마다 먼저 `answer_gist`에 **"이 질문에 답하면 결국 무슨 내용을 설명하게 되나"를 2~3문장으로** 적는다. (질문 표현이 아니라 '답의 알맹이'를 적어라)
   - **한 줄로 줄이지 마라.** 답에 들어갈 핵심 사실(인물·장소·사건·수치·해석)을 실제로 담아라. 이 gist는 지난 질문과 겹치는지 재는 잣대로도 쓰이는데, 짧게 쓸수록 판정이 나빠진다(실측: 한 문장 88% / 답변 수준 100%).
2. 그다음 **answer_gist가 실질적으로 같거나 크게 겹치는 질문들**을 `answer_groups`로 묶는다.

**특히 조심할 패턴 — 같은 대상(숫자·인물·사건·장소)의 '의미/상징성/이유/배경/영향'을 각각 물으면 답이 같다:**
- "다윗이 30세에 오른 것의 **의미**?" / "30세가 성경에서 갖는 **상징성**?" → **같은 묶음** (둘 다 답이 '30세=성숙·준비된 지도자')
- "레갑·바아나의 문화적 배경?" / "그들의 동기?" / "그들의 행동에 대한 반응?" → **한 묶음**
- "다윗 통치의 신학적 의미?" / "다윗 왕권의 정당성?" → 한 묶음
- "백성들의 반응?" / "이스라엘 통합에 미친 영향?" → 한 묶음

반대로 "이스보셋 이름의 뜻?"(어원) / "브에롯은 어떤 곳?"(지명)은 gist가 달라 **서로 다른 묶음**이다.

의심스러우면 두 질문의 `answer_gist`를 나란히 놓고 "이 두 답을 각각 쓰면 독자가 서로 다른 걸 배우나, 같은 걸 두 번 배우나"를 물어라. 같은 걸 배우면 한 묶음이다.

## 출력
`{"evaluations": [{"id":"...", "answer_gist":"답의 알맹이 2~3문장", "verdict":"...", "note":"..."}], "answer_groups": [["id1","id3"], ...]}`
— evaluations는 모든 후보(answer_gist 먼저), answer_groups는 gist가 겹치는 묶음만(2개 이상)."""

_QFIX_WRAPPER = """# 떠오르는 질문 — 질문 부분 교체기 (질문만)

이미 고른 9개 중 **문제가 있는 슬롯의 질문만** 새로 갈아끼운다. **답변은 만들지 않는다.**

입력: `고쳐야_할_슬롯`(각 role_id의 기존 질문+문제), `피해야_할_질문`(나머지 슬롯+과거 질문 전체), `본문_내용`, `관주_연결`, `이미_쓴_자리`(다른 질문이 차지한 절·표현).

## 새 질문에도 출처 기록을 붙여라 (필수)
생성 단계와 똑같이 `verse`·`anchor`·`anchor_type`을 함께 낸다. **코드가 원자료와 대조해 검사하고, 틀리면 그 교체는 버려지고 원래 질문이 그대로 남는다.**
- `anchor_type: "본문"` → `anchor`는 그 절에서 **글자 그대로 복사한** 2~15자
- `anchor_type: "관주"` → `anchor`는 `관주_연결`에 **실제로 적힌** 구절 참조(예: `"시편 8:4"`)
- `anchor_type: "KB"` → `anchor`는 `지식`의 재료 번호를 그대로(예: `"7:인물#2"`), `verse`는 `0`. **본문 글자로는 안 열리는 배경(인물·관습·해석 견해)을 여는 자리라 교체용으로 특히 좋다.**
- **`이미_쓴_자리`에 있는 자리는 쓰지 마라.** 다른 질문이 이미 차지한 절·표현이다. 아직 아무도 안 쓴 절에서 고르면 답이 겹칠 일이 없다.

규칙: 아래 공유 톤·질문 규칙을 따른다. 제목형 한 문장. 요청받은 role_id 전부 채운다.
- 교체 질문은 `피해야_할_질문`과 **답변 내용이 겹치면 안 된다** — 소재·표현만이 아니라 '답을 썼을 때 같은 지식이 나오는가'를 본다. **완전히 다른 각도·카테고리**(어원·지명·인물과거·시대배경·타 성경 연결)의 새 지식을 연다.
- `이미_다룬_5단`이 밝힌 사건·동기, 그리고 **오늘 본문 구절에 답이 그대로 있는 것**(나이·숫자 나열 등)을 되묻지 마라.
- 꼬리를 새로 쓸 땐 그 답이 같은 가지 메인 답에 이미 들어갈 내용이면 안 된다.

출력: `{"fixes": [{"role_id","question","category","topic","verse","anchor","anchor_type"}, ...]}`"""


def _shared(*names):
    return "\n\n---\n\n".join(fp._read(PARTS_DIR / n) for n in names)


def _q_system():
    # {N}은 NUM_CANDIDATES로 치환한다(.format은 JSON 예시의 중괄호를 깨서 못 쓴다).
    # 프롬프트에 숫자를 직접 박아두면 NUM_CANDIDATES를 바꿀 때 조용히 어긋난다.
    wrapper = _Q_WRAPPER.replace("{N}", str(NUM_CANDIDATES))
    return "\n\n---\n\n".join([wrapper, _shared("01_role_tone.md", "03_question_rules.md")])


def _qfix_system():
    return "\n\n---\n\n".join([_QFIX_WRAPPER, _shared("01_role_tone.md", "03_question_rules.md")])


def _judge_system():
    return _JUDGE_WRAPPER


# ===== 스키마 =====
def _q_leaf():
    """verse·anchor는 '출처 기록' — 코드가 본문과 대조해 참·거짓을 판정할 수 있는 유일한 필드다.
    topic은 모델이 자유롭게 짓는 라벨이라, 같은 소재에 다른 라벨을 붙여도 코드가 알 방법이
    없다(2026-07-19: 6절 하나에 질문 3개가 서로 다른 topic 라벨을 달고 통과했다).
    anchor는 '그 절에 실제로 있는 문자열'이라 코드가 검증한다."""
    return ({"question": {"type": "string"}, "category": {"type": "string"}, "topic": {"type": "string"},
             "verse": {"type": "integer"}, "anchor": {"type": "string"},
             "anchor_type": {"type": "string", "enum": ["본문", "관주", "KB", "전날"]}},
            ["question", "category", "topic", "verse", "anchor", "anchor_type"])


def _q_gen_schema(n):
    """대등한 후보 n개를 평평하게 받는다 — 메인/꼬리 계층을 두지 않는다.
    계층을 두면 '꼬리 = 메인의 후속 질문'이 되어 같은 소재로 뭉치는 게 정상 동작이 되고,
    그 순간 서로 다른 지식의 개수가 메인 수(6)에 묶인다."""
    lp, lr = _q_leaf()
    # 2026-08-04 개편 — 개수 하한(minItems 12)을 없앴다.
    #   왜: 프롬프트는 "재료가 얇은 날엔 적게 내도 된다"라고 하는데 스키마가 12개를 강제해
    #   모순이었다. 8/03(6절짜리 단일 장면) 실측에서 13개가 나왔고 그중 12개가 "왜/의도/의미"
    #   형태였다 — 하한을 채우려고 같은 소재에 '왜'를 반복한 것이다. 결과적으로 답이 한 점으로
    #   수렴해 최종 2개까지 무너졌다. 이제 개수는 '관찰'이 정한다.
    #
    # observations를 candidates보다 먼저 받는 이유: 한 번에 "질문 N개"를 요구하면 모델은
    #   가장 쉬운 패턴(인물의 속셈 묻기)으로 몰린다. 절을 하나씩 훑어 '이상한 것'을 먼저
    #   적게 하면 질문이 그 관찰에서 파생돼 자연히 갈라진다. (사장님 자료조사 원칙과 같다:
    #   본문 관찰 먼저, 해석은 나중)
    obs = {"type": "object", "properties": {
               "verse": {"type": "integer"},
               "note": {"type": "string"},
               "kind": {"type": "string", "enum": ["본문", "관주", "전날", "KB"]},
               "ref": {"type": "string"}},
           "required": ["verse", "note", "kind", "ref"], "additionalProperties": False}
    return {"type": "object", "properties": {
                "observations": {"type": "array", "minItems": 6, "maxItems": 20, "items": obs},
                "candidates": {"type": "array", "maxItems": n,
                               "items": {"type": "object", "properties": lp, "required": lr,
                                         "additionalProperties": False}}},
            "required": ["observations", "candidates"], "additionalProperties": False}


def _judge_schema():
    return {"type": "object", "properties": {
                "evaluations": {"type": "array", "items": {"type": "object",
                    "properties": {"id": {"type": "string"},
                                   "answer_gist": {"type": "string"},
                                   "verdict": {"type": "string", "enum": _JUDGE_VERDICTS},
                                   "note": {"type": "string"}},
                    "required": ["id", "answer_gist", "verdict", "note"], "additionalProperties": False}},
                "answer_groups": {"type": "array",
                    "items": {"type": "array", "items": {"type": "string"}}}},
            "required": ["evaluations", "answer_groups"], "additionalProperties": False}


def _qfix_schema(role_ids):
    return {"type": "object", "properties": {
                "fixes": {"type": "array", "items": {"type": "object",
                    "properties": {"role_id": {"type": "string", "enum": role_ids},
                                   "question": {"type": "string"},
                                   "category": {"type": "string"}, "topic": {"type": "string"},
                                   "verse": {"type": "integer"}, "anchor": {"type": "string"},
                                   "anchor_type": {"type": "string", "enum": ["본문", "관주", "KB", "전날"]}},
                    "required": ["role_id", "question", "category", "topic",
                                 "verse", "anchor", "anchor_type"],
                    "additionalProperties": False}}},
            "required": ["fixes"], "additionalProperties": False}


# ===== 중복 판정 헬퍼 (코드) =====
_SAME_DAY_LCS = 0.40


def _dup_same_day(q, topic, pq, pt):
    if fp._overlap(q, pq) or (topic and pt and fp._overlap(topic, pt)):
        return True
    if fp._lcs_ratio_max(q, pq) >= _SAME_DAY_LCS:
        return True
    if topic and pt and fp._norm(topic) == fp._norm(pt):
        return True
    return False


# ===== 지난 질문과의 중복: 글자가 아니라 '뜻'으로, 최근 며칠만 =====
# 0804 실측(사무엘하 34일·질문 306개·46,665쌍, 정답표=답변이 실제 겹치는 17쌍):
#   옛 잣대(질문 글자겹침 0.48) → 17쌍 중 0쌍 적중. 대신 답이 딴판인 6쌍을 잘못 막았다.
#   막힌 6쌍의 날짜 간격은 5·7·21·21·24·26일 — 먼 날짜만 막고 가까운 날은 다 통과시켰다.
#   실제 피해: 8/4 "압살롬이 헤브론을 선택한 이유"가 32일 전 "다윗이 헤브론을 선택한 이유"와
#   글자 0.68로 닮았다는 이유로 탈락(다윗은 하나님께 물어 갔고 압살롬은 상징을 도용 — 답이 정반대).
#   진짜 중복 17쌍은 100%가 3일 이내·같은 장에서 났다(1일 14 / 2일 2 / 3일 1 / 4일 이상 0).
# 임계 0.75 = 걸린 41건을 사장님이 전수 검토한 결과(중복맞음 15·억울함 22·모르겠음 4)에서
#   억울한 차단이 0이 되는 지점. 방침: "중복 차단은 최소한의 장치, 온전히 같은 것만 막는다."
_HIST_WINDOW_DAYS = 3
_HIST_SIM = 0.75
_CORE_SENTS = 3
_CORE_VECS: dict = {}


def _core_shape(text):
    """지난 답변을 gist와 '같은 모양'(앞 2~3문장)으로 자른다 — 길이가 다르면 유사도가 눌린다."""
    parts = [x for x in re.split(r"(?<=[.!?요])\s+", (text or "").strip()) if x]
    return " ".join(parts[:_CORE_SENTS]) if parts else (text or "")


def _days_between(a, b):
    try:
        return abs((datetime.date.fromisoformat(b[:10]) - datetime.date.fromisoformat(a[:10])).days)
    except Exception:
        return None


def _hist_index(history, embed, today, *, log=None):
    """최근 창 안의 지난 질문을 답변 벡터와 함께 색인한다."""
    rows = [h for h in (history or []) if h.get("question")]
    base = today or max((h.get("date", "") for h in rows), default="")
    if base:
        rows = [h for h in rows
                if (_days_between(base, h.get("date", "")) or 0) <= _HIST_WINDOW_DAYS]
    texts = [_core_shape(h.get("answer", "")) for h in rows]
    vecs = [None] * len(rows)
    if embed is not None and any(texts):
        try:
            got = embed([t for t in texts if t])
            it = iter(got)
            vecs = [next(it) if t else None for t in texts]
        except Exception as e:
            if log:
                log(f"  [지난중복] 임베딩 실패 — 대조 건너뜀: {str(e)[:70]}", "WARN")
    return [{"date": h.get("date", ""), "question": h.get("question", ""), "vec": v}
            for h, v in zip(rows, vecs)]


def _hist_dup_embed(core, index):
    """gist가 창 안의 지난 답과 뜻으로 겹치면 그 날짜를 돌려준다. 근거가 없으면 막지 않는다."""
    cv = _CORE_VECS.get(core or "")
    if not cv or not index:
        return None
    best, best_date = 0.0, None
    for row in index:
        if not row["vec"]:
            continue
        sim = _cosine(cv, row["vec"])
        if sim > best:
            best, best_date = sim, row["date"]
    return best_date if best >= _HIST_SIM else None


def _hist_dup(q, topic, history):
    """옛 글자 잣대 — 실측 적중 0/17이라 판정에서 뺐다(호출부 호환용으로만 남긴다)."""
    return None


# ===== 출처 기록(verse·anchor) — 코드가 본문과 대조할 수 있는 유일한 하드 근거 =====
# 왜 필요한가(2026-07-19 실측): 8절짜리 본문에서 1·3·7절은 손도 안 댔는데 6절 하나에
# 질문 3개가 몰렸다. topic 라벨은 셋 다 달라서 코드도 mini도 못 잡았고, 답변 자카드도
# 어휘가 달라 못 잡았다(1↔3 = 0.183). 어휘·라벨은 모델이 마음대로 바꿀 수 있지만,
# '본문 몇 절의 어느 글자에서 나왔나'는 코드가 본문과 대조해 참·거짓을 판정할 수 있다.
_MAX_PER_VERSE = 2   # 한 절에 허용할 최대 질문 수(자리가 정말 모자랄 때만 초과)


def _verse_map(qt):
    """{절번호: 정규화된 절 본문}. 같은 번호가 두 번 나오면(교차장 등) 이어 붙인다."""
    vm = {}
    for v in qt.get("verses", []):
        try:
            n = int(v.get("number"))
        except (TypeError, ValueError):
            continue
        vm[n] = vm.get(n, "") + fp._norm(v.get("text", ""))
    return vm


def _xref_map(qt):
    """{절번호: {정규화된 관주 구절 참조}} — 관주형 출처 기록을 코드가 검증하는 근거.

    모델이 '시편 8:4와 이어진다'고 주장하면, 그 절의 실제 관주 목록에 있는지 대조한다.
    아무 구절이나 갖다 붙이는 걸 막는다."""
    out = {}
    try:
        chapter = qt.get("verses_start_chapter") or qt.get("chapter")
        book = qt.get("book_name", "")
        if not chapter:
            return out
        for v in qt.get("verses", []):
            n = v.get("number")
            if n is None:
                continue
            refs = openbible_xref.lookup_verse(book, int(chapter), int(n), top_n=8, min_votes=2)
            got = set()
            for r in refs:
                ref = r[0] if isinstance(r, (tuple, list)) else r
                got.add(fp._norm(openbible_xref.osis_to_korean(ref) if ":" not in str(ref) else ref))
            out[int(n)] = got
    except Exception:
        return out
    return out


# KB의 '장 전체' 재료들 — 특정 절에 묶이지 않아 본문형·관주형으로는 정박할 자리가 없다.
# key_details는 자체 verse 필드가 있어 본문형으로 이미 쓰이므로 여기 넣지 않는다.
_KB_FIELDS = ("인물", "주의점", "신학_핵심")


def _kb_map(kb):
    """KB 항목에 번호를 매긴 색인 — 'KB형' 출처 기록의 검증 대상.

    왜 필요한가(2026-07-20): `인물`·`주의점`·`신학_핵심`은 장 전체 차원이라 특정 절의
    글자와 묶이지 않는다. 그래서 이 재료로 만든 질문은 정박할 자리가 없어 탈락하거나
    모델이 억지로 절 글자를 갖다 붙였다(삼하 7:18-29 기준 13개 재료가 통째로 사장됐다).
    번호를 붙여 건네고 '몇 번 재료를 썼는지' 답하게 하면, 본문·관주와 똑같이 코드가
    실재 여부를 대조할 수 있다 — 지어내면 걸린다."""
    out = {}
    for _chap, field, key, item in _kb_items(kb):
        out[key] = item
    return out


def _kb_items(kb):
    """(장, 필드, 번호키, 항목)을 훑는다 — 색인과 payload가 **같은 번호**를 쓰도록 한 곳에서 만든다.

    KB는 장 번호가 최상위 키인 구조다(`{"7": {"인물": [...], ...}}`). 크로스챕터인 날은
    장이 둘 이상 오므로 번호에 장을 함께 박는다(`7:인물#1`) — 안 그러면 두 장의 1번이
    같은 자리로 세어진다."""
    if not isinstance(kb, dict):
        return
    for chap, body in kb.items():
        if not (isinstance(chap, str) and chap.isdigit() and isinstance(body, dict)):
            continue
        for field in _KB_FIELDS:
            v = body.get(field)
            if isinstance(v, str):
                if v.strip():
                    yield chap, field, f"{chap}:{field}#1", v
            elif isinstance(v, list):
                for i, item in enumerate(v, 1):
                    yield chap, field, f"{chap}:{field}#{i}", item


def _kb_numbered(kb):
    """모델에게 건네는 KB — `_kb_map`과 똑같은 번호를 붙여 보낸다.
    번호가 보여야 모델이 KB형 출처 기록으로 그 번호를 지목할 수 있다."""
    if not isinstance(kb, dict):
        return kb
    numbered = {}
    for chap, field, key, item in _kb_items(kb):
        numbered.setdefault(chap, {}).setdefault(field, {})[key] = item
    out = {}
    for k, v in kb.items():
        if k in numbered:
            out[k] = {**{f: b for f, b in v.items() if f not in _KB_FIELDS}, **numbered[k]}
        else:
            out[k] = v
    return out


def _anchor_ok(verse, anchor, vmap, atype="본문", xmap=None, kbmap=None):
    """출처 기록이 진짜인가 — 코드가 원자료와 대조한다.

    본문형: anchor가 그 절 본문에 글자 그대로 있는가.
    관주형: anchor가 그 절의 실제 관주 목록에 있는 구절인가.
    KB형: anchor가 우리가 건넨 KB 항목 번호로 실제 존재하는가.
    셋 다 모델이 지어내면 걸린다(topic 라벨과 달리 참·거짓을 판정할 수 있다)."""
    na = fp._norm(anchor)
    if len(na) < 2:
        return False
    if atype == "KB":
        # verse는 보지 않는다 — 장 전체 재료라 절 번호를 요구하면 근거 없는 숫자를
        # 지어내게 되고, 그건 출처 기록의 원칙(검증 가능한 것에만 규칙을 건다)에 어긋난다.
        return na in {fp._norm(k) for k in (kbmap or {})}
    if atype == "관주":
        refs = (xmap or {}).get(verse) or set()
        # '시편 8:4'처럼 정확히 일치하거나, 관주 표기에 포함되면(범위 표기 등) 인정한다.
        return any(na == r or na in r or r in na for r in refs if r)
    # 전날형도 출발점은 '오늘 본문 글자'다 — 본문형과 같은 검사를 받는다.
    # (앞 문맥에서 출발하면 어제 큐티를 거른 독자가 질문을 이해하지 못한다.)
    body = vmap.get(verse)
    return bool(body) and na in body


_REPAIR_MIN = 0.70      # 본문과 이만큼 닮았으면 '옮겨 적다 어긋난 것'으로 보고 고친다


def _norm_map(s):
    """정규화 문자열과 '정규화 위치 → 원문 위치' 대응표. 고친 근거를 원문 글자로 돌려주려고."""
    out, idx = [], []
    for i, ch in enumerate(s or ""):
        n = fp._norm(ch)
        if n:
            out.append(n)
            idx.append(i)
    return "".join(out), idx


def _repair_anchor(c, verses, *, log=None, tag=""):
    """근거가 본문과 어긋나면 버리지 말고 '본문의 실제 글자'로 고쳐서 내보낸다.

    모델은 복사기가 아니라 본문을 읽고 매번 다시 쓴다. 그래서 어긋남이 스펙트럼으로
    나온다 — 절 번호만 틀림(글자 100%) → 낱말 빠뜨림 → 어미 바꿈(85%) → 뜻만 남기고
    다시 씀(50%). 앞의 셋은 지어낸 게 아닌데 예전엔 다 버려서 전날형·배경지식형이
    매일 1개씩 죽었다(0804 실측). 사장님 지시 0805: 대조→틀림→'수정 후 내보냄'.

    반환: True면 c의 verse·anchor가 (필요하면) 본문 글자로 맞춰졌다. False면 못 고침.
    """
    na = fp._norm(c.get("anchor", ""))
    if len(na) < 2:
        return False
    for num, text in verses:                     # ① 글자는 맞고 절 번호만 틀린 경우
        nt, idx = _norm_map(text)
        p = nt.find(na)
        if p >= 0:
            if c.get("verse") != num and log:
                log(f"  [{tag}] 절 번호 교정: {c.get('verse')}절 → {num}절 '{c.get('anchor','')[:16]}'", "INFO")
            c["verse"] = num
            c["anchor"] = text[idx[p]: idx[p + len(na) - 1] + 1]
            return True
    best = (0.0, None, None)                     # ② 조금 어긋난 경우 — 제일 닮은 대목의 원문으로
    for num, text in verses:
        nt, idx = _norm_map(text)
        blocks = [b for b in SequenceMatcher(None, na, nt, autojunk=False).get_matching_blocks() if b.size]
        if not blocks:
            continue
        cov = sum(b.size for b in blocks) / len(na)
        if cov > best[0]:
            s, e = blocks[0].b, blocks[-1].b + blocks[-1].size - 1
            best = (cov, num, text[idx[s]: idx[e] + 1])
    if best[0] >= _REPAIR_MIN:
        if log:
            log(f"  [{tag}] 근거를 본문 글자로 교정(일치 {best[0]:.0%}): "
                f"'{c.get('anchor','')[:16]}' → {best[1]}절 '{best[2][:20]}'", "INFO")
        c["verse"], c["anchor"] = best[1], best[2]
        return True
    if log:
        log(f"  [{tag}] 본문과 너무 달라 버림(일치 {best[0]:.0%}): '{c.get('anchor','')[:20]}'", "WARN")
    return False


def _slot_desc(c, cut=None):
    """차지한 자리를 사람·모델이 읽는 말로. KB형은 절 번호가 0이라 '0절'로 쓰면 헷갈린다."""
    a = c.get("anchor", "")
    a = a[:cut] if cut else a
    if c.get("anchor_type") == "KB":
        return f"KB '{a}'"
    return f"{c.get('verse')}절 {c.get('anchor_type', '본문')} '{a}'"


def _anchor_key(c):
    """'차지한 자리' 식별자. 같은 절이라도 본문형과 관주형은 서로 다른 자리다
    (18절 '여호와 앞에 앉아'와 18절↔시편 8:4 연결은 답이 완전히 다르다).
    검증 실패한 후보는 자리를 주장할 수 없다(None)."""
    return (c["verse"], c.get("anchor_type", "본문"), fp._norm(c["anchor"])) if c["anchor_ok"] else None


def _vslot(c):
    """차지한 절 번호. 검증 실패한 후보는 절도 주장할 수 없다(None).

    이걸 None으로 안 막으면 정반대 사고가 난다 — 본문에 없는 절(2026-07-13 실측:
    본문은 6:1-11인데 모델이 '17절'을 댔다)은 사용 횟수가 영원히 0이라 '아무도 안 쓴
    가장 신선한 자리'로 보여 1순위로 뽑힌다. 근거를 지어낸 후보가 되레 우대받는다.

    KB형은 장 전체 재료라 특정 절을 차지하지 않는다. 그렇다고 전부 None으로 묶으면
    KB 질문 여러 개가 '같은 자리'로 세어져 두 번째부터 불이익을 받는다 — 재료마다
    별개의 자리를 준다(절 번호와 섞이지 않게 접두사를 붙인다)."""
    if not c["anchor_ok"]:
        return None
    if c.get("anchor_type") == "KB":
        return f"KB:{fp._norm(c['anchor'])}"
    return c["verse"]


# ===== ① 후보 생성 (mini) =====
def _xref_text(qt, log=None):
    """그날 각 절과 이어지는 다른 성경 구절(OpenBible 관주). 로컬 zip 조회 — API 비용 0원.

    왜 넣나(2026-07-20): 짧고 한 주제로 이어진 본문(예: 삼하 7:18-29, 다윗의 기도 12절)은
    본문 글자만으로는 서로 다른 질문거리가 9개쯤에서 바닥난다. 실제로 그날 모델은 22개를
    채우라는 요구에 같은 질문을 2~3번 복사해서 냈다. 관주는 이미 저장소에 있는데(2MB,
    34만 건) KB를 만들 때만 쓰이고 질문 단계엔 전달되지 않고 있었다."""
    try:
        nums = [v.get("number") for v in qt.get("verses", []) if v.get("number") is not None]
        chapter = qt.get("verses_start_chapter") or qt.get("chapter")
        if not (nums and chapter):
            return None
        text = openbible_xref.build_chapter_xref_text(
            qt.get("book_name", ""), int(chapter), nums, top_n=4, min_votes=3)
        if not text:
            return None
        # 머리말은 generate_kb용 지시문("[배경] 항목의 근거로 쓰라", confidence 운운)이라
        # 질문 프롬프트에는 맞지 않는 잡음이다. 절별 연결 줄만 남기고 안내는 새로 붙인다.
        lines = [ln for ln in text.splitlines() if ln.startswith("- ")]
        if not lines:
            return None
        if log:
            log(f"  [simple] 관주 연결 {len(lines)}개 절 첨부", "INFO")
        return ("그날 각 절과 이어지는 다른 성경 구절이다(표=사람들이 매긴 중요도). "
                "'연결 질문' 각도의 근거로 쓸 수 있다. 단 연결된 구절의 내용을 지어내지 마라.\n"
                + "\n".join(lines))
    except Exception as e:   # 관주는 있으면 좋은 재료일 뿐 — 실패해도 질문 생성은 진행한다
        if log:
            log(f"  [simple] 관주 조회 실패(무시하고 진행): {e}", "WARN")
        return None


_BACKGROUND_WRAPPER = """# 떠오르는 질문 — 배경지식형 전용 생성기

오늘 본문에 나오는 **낯선 것의 정체**를 밝히는 질문을 **재료가 있는 만큼만** 만든다(최대 4개). 답변은 만들지 않는다.

## 없으면 만들지 마라 (가장 중요)
배경지식은 **매일 있는 게 아니다.** 그날 재료가 없으면 **빈 목록을 내라. 그건 실패가 아니다.**
- 본문에 **장소 이름이 안 나오면** 지명 질문은 없다.
- `지식`에 **어원 자료가 없으면** 원어 질문은 만들지 마라. 원어 뜻을 짐작해서 쓰면 거짓이 된다.
- `지식`에 인물·관습 재료가 없고 본문으로도 확인이 안 되면 그 갈래는 건너뛴다.
- **1개만 나와도 정상이고, 0개도 정상이다.** 개수를 채우려고 아는 척하지 마라.

## 네 갈래에서 골고루 (가능한 것만)
- **지명** — 본문에 나오는 장소. 어디쯤이고 어떤 곳이었나
- **어원** — 본문에 실제로 적힌 낱말·이름의 원어 뜻이나 유래
- **문화·관습** — 그 행동·물건·절차가 당시에 무엇이었나 (제도·법·의식)
- **인물 배경** — 본문 인물의 정체·과거·관계
- **번역·사본** — 개역개정의 어떤 낱말이 다른 번역·사본과 갈리는 곳

**같은 갈래로 몰지 마라.** 넷 중 서로 다른 갈래로 채운다.

## 왜 이 갈래인가 (실측)
답이 '사실'이라 서로 안 겹친다 — 답 겹침 비율이 어원 0% · 지명 0% · 인물 8% · 문화 13%다.
반면 속셈·의미를 묻는 질문은 48~55%가 겹친다. **이 갈래가 그날 질문을 살린다.**

## 반드시 지킬 것
- `anchor`는 오늘 본문 절에서 **글자 그대로 복사한 2~15자**(그 낯선 것이 나오는 대목). 코드가 대조한다.
- **속셈을 묻지 마라.** "왜 그랬나 / 무슨 의도인가"는 이 생성기의 일이 아니다.
  - ✗ "압살롬이 병거와 말을 준비한 이유는 무엇인가요?" (속셈)
  - ✓ "왕이 아닌 사람이 병거와 호위병을 두는 게 당시에 허용된 일이었나요?" (제도)
  - ✗ "성문에서 송사를 들은 이유는?" (속셈)
  - ✓ "재판이 왜 하필 성문에서 열렸나요?" (관습)
  - ✓ "'마음을 훔치다'는 히브리 원어로 어떻게 적혀 있나요?" (어원)
- **`지식`에 없는 원어 뜻·현대 지명·역사 추정을 지어내지 마라.** 근거가 없으면 그 갈래는 건너뛴다.
- **번역·사본은 특히 조심하라.** 그 구절 하나의 문제인지 성경 전반의 현상인지 구분해라. **"성경에서 종종 ~한다"처럼 일반화하지 마라** — 실제로 이 자리에서 거짓이 나갔다(2026-08-04: 삼하 15:7 한 곳의 사본 차이를 "성경에서 종종 발견돼요"라고 적었다). 근거가 확실하지 않으면 이 갈래는 만들지 마라.
- 장절 번호·마크다운(`**`) 금지. `같은_책_기존_STEP2_질문`의 소재는 피한다.

## 출력
`{"candidates": [{"question","category","topic","verse","anchor"}]}` — **0~4개**(재료가 있는 만큼).
`category`는 `"지명 정보"`·`"어원·유래"`·`"문화·관습"`·`"인물 배경"`·`"번역·사본"` 중 하나."""


def _background_schema():
    return {"type": "object", "properties": {
        "candidates": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {
            "question": {"type": "string"},
            "category": {"type": "string",
                         "enum": ["지명 정보", "어원·유래", "문화·관습", "인물 배경", "번역·사본"]},
            "topic": {"type": "string"}, "verse": {"type": "integer"}, "anchor": {"type": "string"}},
            "required": ["question", "category", "topic", "verse", "anchor"],
            "additionalProperties": False}}},
        "required": ["candidates"], "additionalProperties": False}


def _gen_background(chat, qt, kb, history, total_cost, log=None):
    """배경지식(지명·어원·문화·인물) 전용. 본체에 맡기면 '왜 그랬나'로 몰려 이 갈래가 0개가 된다
    (0803 실측: 후보 6개 전부 해석형, 배경지식 0). 사장님 지적대로 종류마다 제 몫을 만들게 한다."""
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "지식": _kb_numbered(kb),
               "같은_책_기존_STEP2_질문": [h.get("question", "") for h in (history or [])[:60]]}
    try:
        data, cost = chat(Q_MODEL, _BACKGROUND_WRAPPER, payload, "followup_background",
                          _background_schema(), 0.7, 1800)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [배경지식] 생성 실패 — 건너뜀: {str(e)[:70]}", "WARN")
        return []
    verses = [(v["number"], v["text"]) for v in qt.get("verses", [])]
    out = []
    for c in (data.get("candidates") or [])[:4]:
        c["anchor_type"] = "본문"
        c["question"] = re.sub(r"\*+", "", c.get("question", "")).strip()
        if not _repair_anchor(c, verses, log=log, tag="배경지식"):
            continue
        out.append(c)
    if log:
        cats = ", ".join(c.get("category", "") for c in out) or "없음"
        log(f"  [배경지식] {len(out)}개 확보 ({cats})", "INFO")
    return out


_GWANJU_WRAPPER = """# 떠오르는 질문 — 관주형(다른 성경 구절로 여는 질문) 전용 생성기

오늘 본문의 한 대목을 **관주 구절이 밝혀 주는 배경**으로 여는 질문을 **2~3개** 만든다. 답변은 만들지 않는다.

## 반드시 지킬 것
- `anchor`는 `관주_연결`에 **실제로 적힌 구절 참조를 그대로** 쓴다(예: `"열왕기상 1:5"`). 목록에 없는 걸 적으면 탈락한다.
- `verse`는 그 관주가 달린 **오늘 본문 절 번호**.
- **질문에 관주의 알맹이가 드러나야 한다.** 무엇을 알게 될지 보여야 독자가 눌러본다.
- **장절 번호를 질문에 쓰지 마라.** 초신자는 '사사기 15:4-5'가 뭔지 모른다. 내용을 풀어 써라.
- 답을 미리 흘리지 마라. 마크다운(`**`) 금지. `같은_책_기존_STEP2_질문`의 소재는 피한다.

## 가장 중요 — 관주에 나오는 '이름'을 질문에 넣어라

관주 구절에 나오는 **인물·장소·사건의 이름을 질문 문장에 그대로 써라.** 그게 이 질문의 알맹이다.
- 왕상 1:5 → **아도니야** · 삿 9:29 → **아비멜렉** · 왕상 3:9 → **솔로몬** · 시 41:9 → **다윗이 쓴 시**

**아래 표현은 쓰지 마라 (코드가 잡아내 버린다).**
`다른 성경 구절` · `성경적 배경` · `성경의 다른 ~사건` · `성경에서 어느 순간` · `어떤 성경 구절` · `다른 성경 사건`
이런 말은 **재료의 이름을 감추는 표현**이다. 독자는 무엇을 알게 될지 모르니 안 눌러본다.

- ✗ "다윗이 지혜롭다는 평가는 어떤 **성경적 배경**을 가지고 있나요?" (왕상 3:9를 받고도 솔로몬을 안 씀)
  → ✓ "지혜를 구한 왕이 다윗 말고 또 있었나요?"
- ✗ "아히도벨이 돌아선 사건은 **성경에서 어느 순간**과 유사한가요?" (시 41:9를 받고도 안 씀)
  → ✓ "다윗이 '믿던 친구가 나를 배반했다'고 노래한 시가 있는데, 누구를 두고 쓴 걸까요?"
- ✗ "**성경의 다른 왕위 계승 사건**과 어떤 점에서 닮았나요?" (왕상 1:34를 받고도 솔로몬을 안 씀)
  → ✓ "나팔을 불어 왕이 되었다고 알린 사람이 압살롬 말고 또 있나요?"

## 뭉개지 마라
관주 구절을 받아놓고 "다른 성경 구절과 연결되나요"라고 물으면 **그 재료를 통째로 버리는 것**이다. 실제로 이런 실패가 반복됐다.

- 관주 = 왕상 1:5(다윗의 또 다른 아들 아도니야도 병거와 오십 명을 준비함)
  - ✗ "압살롬의 행동은 다윗 왕국의 정치적 불안정과 어떻게 연결되나요?" (아도니야가 한 글자도 없다)
  - ✓ "다윗의 또 다른 아들도 병거와 오십 명을 준비한 적이 있나요?"
- 관주 = 사사기 15:4-5(삼손이 여우 꼬리에 불을 붙여 블레셋 밭을 태움)
  - ✗ "요압의 밭에 불을 지른 사건과 사사기 15:4-5의 사건은 어떻게 연결되나요?" (장절만 대서 궁금하지 않다)
  - ✓ "남의 밭에 불을 지른 일이 성경에 또 있나요?"
- 관주 = 삼하 12:7(나단이 다윗에게 "당신이 그 사람이라")
  - ✗ "여인이 전한 이야기는 어떤 성경 구절과 연결되나요?"
  - ✓ "다윗이 남의 이야기를 듣다가 자기 이야기인 걸 깨달은 적이 또 있나요?"

## 두 번째로 중요 — 오늘 본문의 낱말을 질문 안에 그대로 박아라

`hook`에 **오늘 본문 절에서 글자 그대로 복사한 2~10자**를 적고, **그 소재를 질문 문장에서 실제로 다뤄라.**
코드가 대조한다 — hook이 본문에 없거나 질문이 본문과 한 조각도 안 겹치면 버려진다. (어미는 바뀌어도 된다.)

**그 절에서 가장 눈에 띄는 물건·장소·행동을 골라라.**
- ✓ `hook: "병거와 말들"` → 질문 "…병거와 오십 명을 준비한 적이 있나요?"
- ✓ `hook: "재판관이 되고"` → 질문 "…재판관이 되겠다고 선언한 적이 있나요?"
- ✓ `"성문 곁"` · `"사십 년"` · `"이스라엘 모든 지파"` · `"나팔 소리"` · `"땅에 쏟아진 물"`

이 규칙이 있는 이유 — 오늘 본문의 물건·장소·말이 질문에 없으면, 관주가 교리 구절일 때 질문이 이렇게 흘러간다.
- ✗ (삼하 14:14 ↔ 히브리서 9:27을 받고) "사람이 죽음을 피할 수 없다는 점에서 성경은 어떤 교훈을 주나요?"
  → 오늘 본문 낱말이 하나도 없다. 아무 날에나 붙는 설교가 됐다.
  → ✓ `hook: "땅에 쏟아진 물"` — "여인이 말한 '땅에 쏟아진 물'은 무엇을 두고 한 말인가요?"

**'교훈·가르침·의미·시사점'을 묻지 마라.** 오늘 본문의 그 낱말이 무엇인지·누구와 닮았는지를 물어라.

## 무엇을 여는 질문인가
오늘 본문에 나오지만 초신자가 모를 것을 관주로 밝힌다 — ⓐ 낯선 인물의 정체 ⓑ 본문이 빗대는 옛 사건 ⓒ 그 행동·판결의 근거가 된 율법·관습.

## 만들 수 없으면 적게 내라
쓸 만한 관주가 1개뿐이면 1개만 낸다. 억지로 채우려고 뭉개지 마라.
`hook`을 질문에 못 넣을 관주라면, 그 관주는 오늘 본문과 직접 이어지지 않는다는 뜻이다 — 빼라.

## `이름` 칸 — 관주 구절에 나오는 인물·장소 이름

`이름`에 **그 관주 구절에 실제로 나오는 인물이나 장소의 이름**을 적고, **질문 문장에도 그 이름을 쓴다.**
- 왕상 1:5 → `"아도니야"` · 삿 9:29 → `"아비멜렉"` · 왕상 3:9 → `"솔로몬"` · 시 41:9 → `"다윗"`

**이름이 없는 관주면 빈 문자열을 적어라.** 지어내지 마라. 롬 16:18('부드러운 말로 순진한 자의 마음을
미혹하느니라')처럼 인물이 안 나오는 구절이 있다 — 그런 날은 빈 값이 정답이다. 빈 값이라고 탈락하진
않지만, 이름 있는 관주가 있으면 그쪽이 먼저 뽑힌다.

## 출력
`{"candidates": [{"question","topic","verse","anchor","hook","이름"}]}` — 1~3개. `topic`은 1~4단어 소재 라벨."""


# 뭉개기 표현 — 관주 재료의 이름을 감추는 말들. 프롬프트로만 막으니 안 지켜졌다
# (0804 실측: 관주 10개 중 4개가 이 형태. 같은 날 8/03만 아도니야·아비멜렉을 제대로 넣었다).
# 주의: '비슷한 사건이 성경에 또 있나요?'처럼 궁금증이 남는 표현은 걸리지 않게 좁게 잡는다.
_VAGUE_REF = re.compile(
    r"다른\s*성경\s*(구절|사건|이야기)"
    r"|성경적\s*배경"
    r"|성경의\s*다른"
    r"|성경에서\s*(어느|어떤)"
    r"|어떤\s*성경\s*구절"
    r"|다른\s*구절과\s*(어떻게|어떤)")


def _gwanju_schema():
    return {"type": "object", "properties": {
        "candidates": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
            "question": {"type": "string"}, "topic": {"type": "string"},
            "verse": {"type": "integer"}, "anchor": {"type": "string"},
            "hook": {"type": "string"}, "이름": {"type": "string"}},
            "required": ["question", "topic", "verse", "anchor", "hook", "이름"],
            "additionalProperties": False}}},
        "required": ["candidates"], "additionalProperties": False}


_HOOK_RUN = 4      # 질문과 본문이 이만큼 이어져 겹치면 '본문에서 출발한 질문'으로 본다


def _hook_ok(c, vmap, body_all):
    """오늘 본문의 구체 표현이 질문 안에 실제로 들어갔는가 — 코드가 대조한다.

    관주가 교리 구절(히 9:27 '한번 죽는 것은 사람에게 정해진 것')이면 질문에 넣을
    인물·사건 이름이 없어서 '어떤 교훈을 주나요'로 흘렀다(0804 실측). 오늘 본문
    낱말을 질문에 박게 하면 그 미끄러짐이 막힌다 — 책 종류로 관주를 거르는 것보다
    정확하다(시편 41:9는 교리서가 아닌데도 아히도벨과 직결되는 좋은 재료였다).

    검사는 두 단계다.
    1) `hook`이 그 절 본문에 글자 그대로 있는가 — 지어낸 소재를 막는다.
    2) 질문이 본문과 4글자 이상 이어져 겹치는가 — hook 자체를 질문에서 찾지는
       않는다. 한국어는 어미가 붙어서('재판관이 되고' → '재판관이 되겠다고')
       통째 대조하면 멀쩡한 질문이 죽는다. 0804 실측: 아도니야·아비멜렉·시편41편
       질문이 전부 이 이유로 탈락했다."""
    hk = fp._norm(c.get("hook", ""))
    if len(hk) < 2 or hk not in (vmap.get(c.get("verse")) or ""):
        return False
    q = fp._norm(c.get("question", ""))
    return any(q[i:i + _HOOK_RUN] in body_all for i in range(len(q) - _HOOK_RUN + 1))


def _gen_gwanju(chat, qt, history, total_cost, log=None):
    """관주형 = 다른 성경 구절이 밝혀 주는 배경. (지명·어원·문화·인물을 다루는
    배경지식형과는 다른 갈래다 — 이름이 겹쳐 헷갈렸던 부분을 0804에 정리했다.)
    전용 호출로 뺀다. 본체 프롬프트에 규칙만 두면 '다른 성경 구절과 연결되나요' 같은
    뭉개기가 반복됐다(0801 두 건·0803 한 건 — 받은 관주는 아도니야·나단·아비멜렉이었는데
    질문에 한 글자도 안 들어갔다). 전날형을 전용 호출로 뺐더니 해결된 것과 같은 처방."""
    xtext = _xref_text(qt, log=log)
    if not xtext:
        return []
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "관주_연결": xtext,
               "같은_책_기존_STEP2_질문": [h.get("question", "") for h in (history or [])[:60]]}
    try:
        data, cost = chat(Q_MODEL, _GWANJU_WRAPPER, payload, "followup_gwanju",
                          _gwanju_schema(), 0.7, 1600)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [관주형] 생성 실패 — 건너뜀: {str(e)[:70]}", "WARN")
        return []
    xmap = _xref_map(qt)
    vmap = {v["number"]: fp._norm(v["text"]) for v in qt.get("verses", [])}
    body_all = "".join(vmap.values())
    out = []
    for c in (data.get("candidates") or [])[:3]:
        c["anchor_type"] = "관주"
        c["category"] = "관주"
        c["question"] = re.sub(r"\*+", "", c.get("question", "")).strip()
        if not _anchor_ok(c.get("verse"), c.get("anchor", ""), {}, "관주", xmap):
            if log:
                log(f"  [관주형] 관주 목록에 없어 버림: {c.get('verse')}절 '{c.get('anchor','')}'", "WARN")
            continue
        if _VAGUE_REF.search(c["question"]):
            if log:
                log(f"  [관주형] 뭉개기 표현으로 버림: '{c['question'][:44]}'", "WARN")
            continue
        nm = (c.get("이름") or "").strip()
        # 이름은 탈락 조건이 아니라 순위 재료다 — 이름 없는 관주(롬 16:18 같은 교리 구절)도
        # 그날 재료가 그것뿐이면 써야 한다. 다만 이름 있는 쪽이 먼저 뽑힌다.
        c["named"] = bool(nm and fp._norm(nm) in fp._norm(c.get("question", "")))
        if not _hook_ok(c, vmap, body_all):
            if log:
                log(f"  [관주형] 본문 표현이 질문에 없어 버림: '{c.get('hook','')}' "
                    f"← '{c['question'][:38]}'", "WARN")
            continue
        out.append(c)
    if log:
        log(f"  [관주형] {len(out)}개 확보" + ("".join(
            f" · {c['verse']}절↔{c['anchor']}" + (f"({c['이름']})" if c.get("named") else "(이름없음)")
            for c in out)
                                            if out else " (쓸 만한 관주 없음)"), "INFO")
    return out


_PREVDAY_WRAPPER = """# 떠오르는 질문 — 전날형(앞 문맥형) 전용 생성기

오늘 본문의 한 대목이 **바로 앞 며칠 본문에서 이어져 온 것**임을 여는 질문을 **1개만** 만든다. 답변은 만들지 않는다.

## 이 질문의 조건 (넷 다 지켜야 한다)
1. **출발점이 오늘 본문 문장이다.** `anchor`는 오늘 본문 절에서 **글자 그대로 복사한 2~15자**. 코드가 대조해 검사하고 틀리면 버려진다.
2. **어제 큐티를 거른 사람도 오늘 본문만 읽고 질문이 이해돼야 한다.** 앞 내용을 질문에 담지 마라 — 답에서 밝힌다.
3. **답이 실제로 `최근_본문`을 필요로 해야 한다.** 오늘 본문만으로 답이 끝나면 실패다.
   → 이걸 스스로 증명해라: `link`에 **답이 가리키는 `최근_본문`의 `본문_참조`를 그대로** 적는다(예: `"사무엘하 15:1-6"`). 목록에 없는 걸 적으면 탈락한다. 가리킬 데가 없으면 그 질문은 만들지 마라.
4. `같은_책_기존_STEP2_질문`에 있는 소재는 피한다.
5. **마크다운을 쓰지 마라.** `**굵게**`·따옴표 강조 금지 — 질문은 맨 문장 하나다.

## 예시 (이 형태를 그대로 따라라)
오늘 본문이 삼하 15:7-12이고 어제가 15:1-6(압살롬이 성문에서 민심을 얻음)일 때 —
- ✗ "압살롬이 **앞서 백성의 마음을 얻은 일**은 오늘의 반역과 어떻게 이어지나요?"
  → 출발점이 오늘 본문 밖. 어제를 안 읽으면 무슨 말인지 모른다.
- ✗ "압살롬은 왜 헤브론을 골랐나요?" → 오늘 본문만으로 답이 끝난다(그냥 본문형).
- ✓ "압살롬에게로 **돌아온 백성**은 그날 갑자기 마음을 바꾼 걸까요?"
  → `verse: 12, anchor: "돌아오는 백성이 많아지니라"`. 오늘 문장에서 출발하고, 답이 어제 성문 장면으로 이어진다.
- ✓ "압살롬은 어떻게 **이스라엘 모든 지파**에 전령을 보낼 수 있었을까요?"
  → `verse: 10, anchor: "이스라엘 모든 지파"`. 연락망이 이미 있었다는 뜻 → 답이 어제로 간다.

## 만들 수 없으면 만들지 마라
오늘 본문에 '앞에서 이어져 온 흔적'이 없으면(장면 한복판이라 앞뒤가 한 덩어리인 날 등) **빈 목록을 내라.** 억지로 만들면 없는 연결을 지어내게 된다. 이건 실패가 아니다.

## 출력
`{"candidates": [{"question","category","topic","verse","anchor","link"}]}` — 0개 또는 1개.
`category`는 항상 `"전날"`, `topic`은 1~4단어 소재 라벨, `link`는 답이 가리키는 앞 본문의 참조."""


_REF_RE = re.compile(r"^\s*(\D*?)\s*(\d+)\s*:\s*(\d+)\s*(?:[-~]\s*(\d+))?\s*$")


def _ref_parts(s):
    """'사무엘하 14:1-11' → ('사무엘하', 14, 1, 11). 못 읽으면 None."""
    m = _REF_RE.match(s or "")
    if not m:
        return None
    book, chap, v1, v2 = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4)
    return book, chap, v1, int(v2) if v2 else v1


def _link_in_recent(link, recent_refs):
    """모델이 댄 앞 본문 참조가 최근 본문 '안에' 들어가는가.

    예전엔 글자가 똑같아야만 인정했다. 그래서 모델이 '사무엘하 14:3'처럼 절 단위로
    정확히 짚으면 목록의 '사무엘하 14:1-11'과 글자가 달라 버려졌다(0801·0803 실측 —
    맞는 답인데 형식 때문에 전날형이 0개가 됐다). 이제 장이 같고 절 구간이 겹치면
    인정한다. 책 이름을 생략해도('14:3') 장·절이 맞으면 통과시킨다."""
    lp = _ref_parts(link)
    if not lp:
        return fp._norm(link or "") in {fp._norm(r) for r in recent_refs}
    lb, lc, l1, l2 = lp
    for r in recent_refs:
        rp = _ref_parts(r)
        if not rp:
            continue
        rb, rc, r1, r2 = rp
        if lc != rc or (lb and rb and fp._norm(lb) != fp._norm(rb)):
            continue
        if l1 <= r2 and r1 <= l2:      # 절 구간이 겹치면 같은 대목을 가리킨 것
            return True
    return False


def _prevday_schema():
    return {"type": "object", "properties": {
        "candidates": {"type": "array", "maxItems": 1, "items": {"type": "object", "properties": {
            "question": {"type": "string"}, "category": {"type": "string"}, "topic": {"type": "string"},
            "verse": {"type": "integer"}, "anchor": {"type": "string"}, "link": {"type": "string"}},
            "required": ["question", "category", "topic", "verse", "anchor", "link"],
            "additionalProperties": False}}},
        "required": ["candidates"], "additionalProperties": False}


def _gen_prevday(chat, qt, recent, history, total_cost, log=None):
    """전날형은 본체 프롬프트에 규칙만 넣어서는 한 개도 안 나온다(0801·0804 실측 2회 연속 0개).
    본체 예시가 전부 본문·관주·KB형이라 그쪽으로 쏠린다 — 프로젝트 기록의 '모델은 규칙보다
    예시를 강하게 따른다'와 같은 현상. 그래서 짧은 전용 호출로 따로 뽑는다."""
    if not recent:
        return []
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "최근_본문": recent,
               "같은_책_기존_STEP2_질문": [h.get("question", "") for h in (history or [])[:60]]}
    try:
        data, cost = chat(Q_MODEL, _PREVDAY_WRAPPER, payload, "followup_prevday",
                          _prevday_schema(), 0.6, 1200)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [전날형] 생성 실패 — 건너뜀: {str(e)[:70]}", "WARN")
        return []
    verses = [(v["number"], v["text"]) for v in qt.get("verses", [])]
    links = [r.get("본문_참조", "") for r in recent]
    out = []
    for c in (data.get("candidates") or [])[:1]:
        c["anchor_type"] = "전날"
        c["question"] = re.sub(r"\*+", "", c.get("question", "")).strip()
        if not _repair_anchor(c, verses, log=log, tag="전날형"):
            continue
        # link 검사 = '답이 정말 앞 본문을 필요로 하는가'를 코드가 확인하는 자리.
        # 이게 없으면 모델이 오늘 본문만으로 답이 끝나는 질문을 전날형이라 우긴다(0804 실측).
        if not _link_in_recent(c.get("link", ""), links):
            if log:
                log(f"  [전날형] 앞 본문 참조가 목록에 없어 버림: '{c.get('link','')}'", "WARN")
            continue
        out.append(c)
    if log:
        log(f"  [전날형] {len(out)}개 확보" + (f" — '{out[0]['question'][:34]}'" if out else " (오늘은 실마리 없음)"), "INFO")
    return out


def _gen_candidates(chat, qt, kb, deep5, history, total_cost, log=None, recent=None):
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "오륜_질문": qt.get("oryun_questions", []), "지식": _kb_numbered(kb),
               "관주_연결": _xref_text(qt, log=log),
               "최근_본문": recent or [],          # 전날형(앞 문맥형) 재료 — 최근 며칠 본문
               # 답변까지 실으면 입력이 4.4만 토큰 늘어난다(하루 +190원). 답변은 중복 검사(임베딩)
               # 에만 쓰고, 프롬프트에는 질문만 보낸다.
               "같은_책_기존_STEP2_질문": [h.get("question", "") for h in history],
               "이미_다룬_5단": deep5}
    # 응답이 max_tokens에 잘려 JSON이 깨지는 일이 있어(16개 생성) 재시도한다.
    last_err = None
    for attempt in range(3):
        try:
            data, cost = chat(Q_MODEL, _q_system(), payload, "followup_candidates",
                              _q_gen_schema(NUM_CANDIDATES), 0.75, 8000)
            fp._add_cost(total_cost, cost)
            cands = data.get("candidates") or []
            # 글자가 똑같은 후보는 여기서 버린다. 개수를 맞추려고 복사해 내는 일이 실제로
            # 있었다(2026-07-16: 22개 중 고유 9개, 나머지 13개가 같은 문장의 복사본).
            # 판정에 넘기면 토큰만 쓰고 '중복' 판정을 받아 후보 재고를 갉아먹는다.
            seen, uniq = set(), []
            for c in cands:
                key = fp._norm(c.get("question", ""))
                if key and key not in seen:
                    seen.add(key)
                    uniq.append(c)
            if log and len(uniq) < len(cands):
                log(f"  [simple] 복사된 후보 {len(cands) - len(uniq)}개 제거 "
                    f"(요청 {NUM_CANDIDATES} → 고유 {len(uniq)})", "WARN")
            cands = uniq
            if cands:
                # 하류(_judge·_flatten_pool)는 (메인 + 꼬리들) 묶음 형태를 기대한다.
                # 이제 후보가 다 대등하므로 '꼬리 없는 묶음'으로 넘긴다 — 하류 수정 불필요.
                return [{"idx": i, "main": c, "tails": []} for i, c in enumerate(cands)]
        except Exception as e:
            last_err = e
            if log:
                log(f"  [simple] 후보 생성 시도 {attempt + 1} 실패(재시도): {e}", "WARN")
    raise fp.FollowUpPoolError(f"후보 생성 3회 실패: {last_err}")


def _branch_qs(b):
    return [(b["main"].get("question", ""), b["main"].get("topic", ""))] + \
           [(t.get("question", ""), t.get("topic", "")) for t in b["tails"]]


# ===== ② 판정 (mini): 체3 본문·5단 재진술 + 체2 메인포함 =====
def _judge(chat, qt, deep5, branches, total_cost, log=None):
    cand = []
    for b in branches:
        i = b["idx"]
        cand.append({"id": f"b{i}_m", "종류": "메인", "question": b["main"].get("question", ""),
                     "갈래": b["main"].get("anchor_type", "본문"),
                     "근거": b["main"].get("anchor", "")})
        for j, t in enumerate(b["tails"]):
            cand.append({"id": f"b{i}_t{j}", "종류": "꼬리",
                         "이_꼬리의_메인_질문": b["main"].get("question", ""),
                         "question": t.get("question", ""),
                         "갈래": t.get("anchor_type", "본문"),
                         "근거": t.get("anchor", "")})
    payload = {"본문_내용": fp._body_text(qt), "이미_다룬_5단": deep5, "후보_질문": cand}
    try:
        data, cost = chat(JUDGE_MODEL, _judge_system(), payload, "followup_judge",
                          _judge_schema(), 0.1, 5000)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [simple] 판정 호출 실패 — 전부 '좋음' 취급: {e}", "WARN")
        return {}, {}, {}
    verdicts = {e.get("id"): e.get("verdict", _GOOD) for e in data.get("evaluations", [])}
    # answer_gist("이 질문에 답하면 결국 무슨 내용을 설명하게 되나")는 지금까지 만들어지고
    # 그냥 버려졌다. 저장해두면 (a) 회차별로 판정이 얼마나 흔들리는지 보이고 (b) 이 문장을
    # 임베딩해 '답이 같아질 질문'을 코드가 잡을 수 있는지 검증할 재료가 된다. 추가 비용 0원.
    gists = {e.get("id"): e.get("answer_gist", "") for e in data.get("evaluations", [])}
    # 답 겹치는 묶음 → id별 클러스터 라벨(묶이지 않은 건 자기 id가 클러스터=고유)
    clusters = {}
    for gi, group in enumerate(data.get("answer_groups", [])):
        for cid in group:
            clusters[cid] = f"g{gi}"
    return verdicts, clusters, gists


# ===== ③ 다양성 조합 선택 (묶음 해체 → 카테고리 다양하게 → 느슨한 짝짓기) =====
# STEP2 공식 9개 카테고리(fp.CATEGORIES)로 정규화한다 — 다양성 계산의 기준이다.
#
# 왜 중요한가(2026-07-20 실측): 라벨이 갈라져 있으면 같은 카테고리를 서로 다른 것으로
# 착각해 다양성을 부풀려 평가한다. 실제로 기록 711개에서 '신학/해석 견해' 19건과
# '신학/해석' 14건, '지명' 11건과 '지명 정보' 5건, '연결' 6건과 '연결 질문' 4건이
# 따로 세어지고 있었다. 정규화 결과가 fp.CATEGORIES와 글자까지 같아야 한다.
# (긴 접두어를 먼저 둔다 — startswith로 매칭하므로 '본문 디'가 '본문'보다 앞이어야 한다)
_CANON = {"주석": "주석형/본문관찰", "본문관찰": "주석형/본문관찰", "본문 관찰": "주석형/본문관찰",
          "본문 디": "본문 디테일", "본문디": "본문 디테일", "디테일": "본문 디테일",
          "지명": "지명 정보", "지리": "지명 정보",
          "어원": "어원·유래", "유래": "어원·유래",
          "인물": "인물 배경", "문화": "문화·관습", "관습": "문화·관습",
          "번역": "번역·사본", "사본": "번역·사본",
          "신학": "신학/해석 견해", "해석": "신학/해석 견해",
          "관주": "관주", "전날": "전날", "랜덤": "랜덤",
          # 옛 라벨 흡수 — 모델이 아직 "연결"이라 붙여도 관주로 본다(근거는 anchor가 정한다)
          "연결": "관주"}


def _canon_cat(c):
    c = (c or "").strip()
    for k, v in _CANON.items():
        if c.startswith(k):
            return v
    return c or "기타"


# ===== 카테고리 우선순위 — '취향'이 아니라 중복 대책이다 =====
# 2026-07-20 실측(12회 · 선택 질문 108개): 카테고리별로 '답이 겹친 쌍에 낀 비율'이 극단적으로 갈렸다.
#     어원·유래 0% · 지명 정보 0% · 인물 배경 8% · 문화·관습 13%
#     주석형/본문관찰 29% · 연결 질문 29% · 신학/해석 견해 48% · 본문 디테일 55%
# 즉 '낯선 것의 정체를 알려주는' 질문은 답이 사실이라 서로 안 겹치고, 추상적인 질문은
# 답이 같은 주제로 수렴한다. 그런데 가장 많이 뽑히던 게 신학/해석 견해(23/108)였다.
#
# 주의 — category는 모델이 스스로 붙이는 라벨이라 출처 기록과 달리 코드가 검증할 수 없다.
# 그래서 상한·하한은 전부 '소프트'다: 재료가 없으면 건너뛴다(강제하면 지어낸다).
_CAT_SAFE = ("인물 배경", "문화·관습", "어원·유래", "지명 정보")   # 겹침 0~13%
_SAFE_MIN = 4                     # 최종 9개 중 안전군에서 최소 이만큼(가능할 때만)
_CAT_CAP = {"신학/해석 견해": 2,   # 48% — 지금 평균 2.6개
            "본문 디테일": 2,      # 55%
            "주석형/본문관찰": 2,
            "관주": 3,          # 본문이 얇은 날 여기로 채운다(0803: 본문 6절뿐, 관주는 절마다 6개)
            "전날": 1}          # 하루 1개 — 과거 되짚기가 많아지면 오늘 본문이 얇아진다


def _cat_cap(cat):
    return _CAT_CAP.get(cat, 9)


def _shared_chunk(a, b, minlen=3):
    """두 문장이 공유하는 가장 긴 연속 글자덩어리 길이(정규화 후). 같은 인물·지명(브에롯,
    이스보셋, 헤브론 등)을 공유하는지 잡는다."""
    na, nb = fp._norm(a), fp._norm(b)
    if not na or not nb:
        return 0
    for L in range(min(len(na), 8), minlen - 1, -1):
        for i in range(len(na) - L + 1):
            if na[i:i + L] in nb:
                return L
    return 0


def _relatedness(a, b):
    """메인-꼬리 연관성(0~1). 같은 소재=1, 같은 인물·지명 공유=0.5~0.7, 아니면 문장 LCS."""
    ta, tb = a.get("topic", ""), b.get("topic", "")
    if ta and tb and fp._norm(ta) == fp._norm(tb):
        return 1.0
    if fp._overlap(ta, tb):
        return 0.85
    lcs = fp._lcs_ratio_max(a.get("q", ""), b.get("q", ""))
    chunk = _shared_chunk(a.get("q", ""), b.get("q", ""))  # 공유 고유명사 길이
    if chunk >= 5:
        return max(0.7, lcs)
    if chunk >= 3:
        return max(0.5, lcs)
    return lcs


def _dedup_pool(pool):
    kept = []
    for c in pool:
        if any(_dup_same_day(c["q"], c["topic"], k["q"], k["topic"]) for k in kept):
            continue
        kept.append(c)
    return kept


def _pick_diverse(pool, n, *, used_clusters=None, prefer_main=False, avoid_cats=(),
                  verse_counts=None, used_anchors=None, cats=None):
    """'본문에서 차지한 자리(절·anchor)'를 최우선으로 퍼뜨리며 n개를 고른다.

    자리 → 답 묶음(cluster) → 카테고리 순으로 다양성을 본다. 자리가 최우선인 이유는,
    자리만 코드가 본문과 대조해 검증할 수 있고 나머지는 모델이 붙인 라벨이라서다.
    verse_counts·used_anchors는 호출자가 넘겨 메인·꼬리 선택에 걸쳐 공유한다(안 넘기면
    호출 안에서만 유효 — 그러면 메인이 쓴 절을 꼬리가 다시 쓴다)."""
    used_clusters = set(used_clusters or [])
    verse_counts = Counter() if verse_counts is None else verse_counts
    used_anchors = set() if used_anchors is None else used_anchors
    # cats도 공유해야 한다 — 호출마다 새로 세면 상한 2개가 메인에서 2, 꼬리에서 2로 4가 된다.
    cats = Counter() if cats is None else cats
    picked = []
    remaining = list(pool)
    while len(picked) < n and remaining:
        # 같은 자리(절+anchor)는 문장이 아무리 달라도 무조건 제외 — 여기가 하드게이트다.
        base = [c for c in remaining
                if _anchor_key(c) not in used_anchors
                and not any(_dup_same_day(c["q"], c["topic"], p["q"], p["topic"]) for p in picked)]
        # 근거가 검증된 후보를 먼저 다 쓴다. 검증 실패(본문에 없는 anchor)는 마지막 수단 —
        # 앞 티어에 끼워주면 '없는 절'이 신선한 자리로 둔갑해 1순위가 된다.
        # 카테고리 상한 — 겹침률 높은 카테고리가 자리를 독차지하지 못하게 막는다.
        # 재료가 없어 아무도 안 남으면 상한을 푼다(억지로 만들게 하지 않는다).
        capped = [c for c in base if cats[c["cat"]] < _cat_cap(c["cat"])]
        base = capped or base
        ok = [c for c in base if c["anchor_ok"]]
        tiers = [
            [c for c in ok if c["cluster"] not in used_clusters and verse_counts[_vslot(c)] == 0],
            [c for c in ok if c["cluster"] not in used_clusters
             and verse_counts[_vslot(c)] < _MAX_PER_VERSE],
            [c for c in ok if c["cluster"] not in used_clusters],
            ok,
            [c for c in base if c["cluster"] not in used_clusters],
            base,
        ]
        elig = next((t for t in tiers if t), None)
        if not elig:
            break
        # 안전군(낯선 것의 정체)을 아직 못 채웠으면 그쪽을 먼저 집는다.
        n_safe = sum(cats[k] for k in _CAT_SAFE)
        need_safe = n_safe < _SAFE_MIN
        c = min(elig, key=lambda c: (0 if c["anchor_ok"] else 1,   # 검증된 근거가 언제나 먼저
                                     1 if c.get("gwanju_weak") else 0,  # 뭉갠 관주는 맨 뒤로
                                     0 if (c.get("anchor_type") != "관주" or c.get("named")) else 1,
                                     0 if (need_safe and c["cat"] in _CAT_SAFE) else 1,
                                     verse_counts[_vslot(c)], cats[c["cat"]],
                                     c["cat"] in avoid_cats,
                                     0 if (prefer_main and c["was_main"]) else 1))
        picked.append(c)
        cats[c["cat"]] += 1
        used_clusters.add(c["cluster"])
        verse_counts[_vslot(c)] += 1
        if _anchor_key(c) is not None:
            used_anchors.add(_anchor_key(c))
        remaining.remove(c)
    return picked


_CHAP_VERSE_RE = re.compile(r"\d+\s*:\s*\d+")     # 질문에 노출된 장절 번호 — 초신자는 못 읽는다


def _gwanju_weak(question, atype, vmap):
    """관주 질문인데 ①뭉갰거나 ②장절 번호를 그대로 썼거나 ③오늘 본문 표현이 하나도
    없으면 약한 관주로 본다. 셋 다 관주 전용 생성기에서는 이미 걸러내는 것들인데,
    본문·해석형에서 나온 관주는 그 검사를 안 받아 그냥 통과했다
    (0804 실측: "잠언 29:5가 다윗과 압살롬의 관계에 어떻게 적용될 수 있나요?")."""
    if atype != "관주":
        return False
    if _VAGUE_REF.search(question) or _CHAP_VERSE_RE.search(question):
        return True
    body = "".join((vmap or {}).values())
    q = fp._norm(question)
    return not any(q[i:i + _HOOK_RUN] in body for i in range(len(q) - _HOOK_RUN + 1))


def _pool_item(d, cid, verdicts, clusters, was_main, vmap, xmap, gists=None, kbmap=None):
    verse, anchor = d.get("verse"), d.get("anchor", "")
    atype = d.get("anchor_type", "본문")
    return {"q": d.get("question", ""), "cat": _canon_cat(d.get("category", "")),
            "topic": d.get("topic", ""), "verdict": verdicts.get(cid, _GOOD),
            "cluster": clusters.get(cid, cid), "was_main": was_main, "sel": False,
            "verse": verse, "anchor": anchor, "anchor_type": atype,
            "anchor_ok": _anchor_ok(verse, anchor, vmap, atype, xmap, kbmap),
            # link = 전날형이 '답이 어디로 가야 하는지' 적어 둔 앞 본문 참조. 검증에만 쓰고
            # 버렸더니 답변 단계가 어디를 볼지 몰라 오늘 본문 안에서만 맴돌았다(0804 실측).
            "link": d.get("link", ""),
            # 관주 전용 생성기가 거르는 잣대를 본문·해석형에서 나온 관주도 받게 한다.
            # 다만 버리지 않고 순위만 뒤로 민다 — 본문·해석형은 그날 후보의 절반 이상이라
            # 여기서 통째로 버리면 재료가 얇은 날 최종 개수가 무너진다(0805 판단).
            "gwanju_weak": _gwanju_weak(d.get("question", ""), atype, vmap),
            # 관주 구절의 인물·장소 이름이 질문에 들어갔나 — 들어간 쪽이 훨씬 구체적이다.
            "named": bool(d.get("named")),
            "gist": (gists or {}).get(cid, ""), "from_qfix": False}


def _flatten_pool(branches, verdicts, clusters, vmap, xmap, gists=None, kbmap=None):
    pool = []
    for b in branches:
        i = b["idx"]
        pool.append(_pool_item(b["main"], f"b{i}_m", verdicts, clusters, True, vmap, xmap, gists, kbmap))
        for j, t in enumerate(b["tails"]):
            pool.append(_pool_item(t, f"b{i}_t{j}", verdicts, clusters, False, vmap, xmap, gists, kbmap))
    return pool


# ===== 코드 하드게이트: '같은 대상의 의미↔영향'은 답이 겹친다 → 결정적으로 한 묶음 =====
# mini가 놓쳐도 코드가 못박는다. 사장님이 반복 지적한 겹침이 거의 이 형태였다.
_MEANING_RE = re.compile(r"의미|의의|뜻|이유|까닭|왜|상징|목적|중요")
_EFFECT_RE = re.compile(r"영향|변화|효과|결과|기여|미친|미쳤|달라")
# 소재(대상)로 안 쳐줄 흔한 말 — 이게 겹친다고 같은 대상은 아니다.
_SUBJ_STOP = {"다윗", "이스라엘", "하나님", "여호와", "사람", "백성", "우리", "당신", "무엇", "어떤",
              "어떻게", "누구", "이유", "의미", "의의", "영향", "변화", "효과", "결과", "목적", "중요",
              "관계", "상황", "과정", "때문", "역할", "모습", "방식",
              # 흔한 '프레이밍' 단어 — 이게 겹친다고 같은 대상이 아니다(오탐 방지)
              "통치", "왕위", "왕권", "즉위", "등극", "시대", "나라", "왕국", "지도자", "사건", "역사",
              "대해", "관해", "위해", "통해", "대한"}
_TOK_RE = re.compile(r"[가-힣]{2,}")
_JOSA_RE = re.compile(r"(은|는|이|가|을|를|의|에게|에서|에|과|와|도|으로|로|만|께서|께)$")


def _subject_tokens(*texts):
    out = set()
    for t in texts:
        for w in _TOK_RE.findall(t or ""):
            w = _JOSA_RE.sub("", w)
            if len(w) >= 2 and w not in _SUBJ_STOP:
                out.add(w)
    return out


def _meaning_effect_pair(a, b):
    """같은 대상 + 하나는 의미/이유형·다른 하나는 영향/변화형이면 답이 겹친다.
    어원·지명은 '뜻·위치'라는 사실 조회라 의미↔영향 겹침 대상이 아니므로 제외."""
    if a["cat"] in ("어원·유래", "지명") or b["cat"] in ("어원·유래", "지명"):
        return False
    if not (_subject_tokens(a["q"], a["topic"]) & _subject_tokens(b["q"], b["topic"])):
        return False
    am, ae = bool(_MEANING_RE.search(a["q"])), bool(_EFFECT_RE.search(a["q"]))
    bm, be = bool(_MEANING_RE.search(b["q"])), bool(_EFFECT_RE.search(b["q"]))
    return (am and be) or (ae and bm)


def _gate_clusters(pool, log=None):
    """union-find로 (mini 클러스터) + (의미↔영향 코드 게이트)를 합쳐 최종 지식묶음을 만든다."""
    n = len(pool)
    parent = list(range(n))

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    def union(i, j):
        parent[find(i)] = find(j)

    seen = {}
    for i, c in enumerate(pool):  # 먼저 mini가 준 클러스터끼리 union
        if c["cluster"] in seen:
            union(i, seen[c["cluster"]])
        else:
            seen[c["cluster"]] = i
    for i in range(n):            # 그다음 코드 게이트로 추가 union
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            # ① 같은 대상의 의미↔영향  ② 같은 소재(topic 동일·글자 중복) — 판정 모델이
            # 놓친 겹침을 코드가 못박는다. 예전엔 ②를 _dedup_pool이 '후보 삭제'로 처리했는데,
            # 그러면 그 묶음의 유일한 후보가 사라져 고를 수 있는 서로 다른 소재가 줄어든다
            # (2026-07-14 실측: 좋음 12개·묶음 9개였는데 삭제로 8개가 되어, 어쩔 수 없이
            #  같은 묶음을 3번 뽑았고 그중 두 질문의 답이 0.88로 겹쳤다).
            # 삭제 대신 '같은 묶음으로 합치기'로 바꾸면 후보는 남되 둘이 같이 뽑히진 않는다.
            why = ("의미↔영향" if _meaning_effect_pair(pool[i], pool[j])
                   else "같은 소재" if _dup_same_day(pool[i]["q"], pool[i]["topic"],
                                                 pool[j]["q"], pool[j]["topic"]) else None)
            if why:
                if log:
                    log(f"  [simple] {why} 게이트 병합: '{pool[i]['q'][:16]}…' ≡ '{pool[j]['q'][:16]}…'", "INFO")
                union(i, j)
    for i, c in enumerate(pool):
        c["cluster"] = f"c{find(i)}"
    return pool


def _assemble_diverse(pool, history, log=None):
    """묶음 해체 → 답 겹침(cluster) 안 되게 + 카테고리 다양하게 메인3·꼬리6 선택 → 느슨히 짝짓기."""
    # 겹치는 후보를 여기서 '삭제'하지 않는다 — 겹침은 _gate_clusters가 이미 같은 묶음으로
    # 합쳐놨고, 선택 단계가 묶음당 하나만 뽑는다. 삭제하면 그 묶음의 유일한 후보까지 날아가
    # 고를 수 있는 소재 수가 오히려 줄어든다(2026-07-14 실측: 묶음 9개 → 8개).
    # 관주·전날은 판정 결과가 나빠도 '본문재진술'만 아니면 살린다. 판정기는 오늘 본문·5단만
    # 보고 판단하는데 이 두 갈래는 답이 본문 밖(다른 성경 구절·앞 며칠 본문)에 있어서
    # 구조적으로 불리하다(0805 실측 8/02: 관주 2·전날 1이 전부 '얕음'·'5단재진술'로 빠져
    # 예약이 통째로 해제됐다). 판정 프롬프트에도 예외를 넣었지만 코드로 한 겹 더 받친다.
    _RESCUE = ("관주", "전날")
    clean = [c for c in pool
             if not c.get("hist_dup")
             and (c["verdict"] == _GOOD
                  or (c.get("anchor_type") in _RESCUE and c["verdict"] != "본문재진술"))]
    if len(clean) < 9:  # 깨끗한 게 모자라면 플래그된 것 중 덜 나쁜 걸 보충(드문 경우)
        clean = clean + [c for c in pool if c not in clean][: 9 - len(clean)]

    # 자리(절·anchor) 사용 현황은 메인·꼬리 선택에 걸쳐 공유해야 한다 — 따로 두면
    # 메인이 쓴 절을 꼬리가 그대로 다시 쓴다.
    verse_counts, used_anchors, cat_counts = Counter(), set(), Counter()
    # §8 소프트 예약: 검증된 관주(배경지식형) 후보 1개를 메인3 고정칸에 먼저 배치한다.
    # 관주는 '오늘 본문 밖' 구절이라 나머지 메인·꼬리와 소재가 구조적으로 안 겹친다 →
    # STEP2 중복의 상당수(메인3 블록발)를 없앤다. 그날 검증된 관주 후보가 없으면 예약을
    # 자동 해제한다(억지로 만들면 없는 연결을 지어낸다). 예약분을 먼저 자리·카테고리 카운터에
    # 반영한 뒤 나머지 2개를 뽑으므로 _pick_diverse의 자리·묶음·상한과 충돌하지 않는다.
    # 관주형과 전날형은 '오늘 본문 밖'을 근거로 삼아 나머지 질문과 소재가 구조적으로 안 겹친다.
    # 그래서 이 둘을 메인 자리에 먼저 앉힌다(사장님 방침 0804: "확정적으로 중복이 안 나오는
    # 고퀄리티 질문을 우선 선별"). 그날 재료가 없으면 각각 자동 해제한다 — 억지로 채우면 지어낸다.
    # 관주를 2개까지 예약한다 — 1개만 잡아 두니 확보한 3개 중 '제일 약한 것'이 뽑히는 일이
    # 벌어졌다(0804 실측 8/03: 아도니야·아비멜렉·롬16:18 중 롬16:18만 최종에 들어감).
    # 뽑는 잣대(_pick_diverse)는 절·묶음·카테고리만 보고 질문 품질은 안 보기 때문이다.
    # 자리를 2개 주면 셋 중 둘이 들어가 '약한 것만 남는' 경우가 사라진다.
    reserved = []
    for atype, want, label in (("관주", 2, "관주"), ("전날", 1, "전날(앞 문맥)")):
        pick = _pick_diverse([c for c in clean if c.get("anchor_type") == atype and c["anchor_ok"]
                              and c not in reserved],
                             want, prefer_main=True, verse_counts=verse_counts,
                             used_anchors=used_anchors, cats=cat_counts)
        for p in pick:
            reserved.append(p)
            if log:
                log(f"  [simple] {label} 메인 예약: '{p['q'][:28]}' "
                    f"({p['verse']}절↔{p['anchor']})", "INFO")
        if not pick and log:
            log(f"  [simple] {label} 예약 해제 — 검증된 후보 없음(정상)", "INFO")
    if reserved:
        reserved = reserved[:3]                  # 메인은 3자리뿐 — 넘치면 앞의 것부터
        others = _pick_diverse([c for c in clean if c not in reserved], 3 - len(reserved),
                               prefer_main=True, verse_counts=verse_counts,
                               used_anchors=used_anchors, cats=cat_counts)
        mains = (others + reserved)[:3]          # 예약분을 메인 뒤쪽 슬롯에 고정
    else:
        mains = _pick_diverse(clean, 3, prefer_main=True, verse_counts=verse_counts,
                              used_anchors=used_anchors, cats=cat_counts)
        if log:
            log("  [simple] 우선 예약 없음 — 관주·전날 후보가 둘 다 없어 일반 선별로 진행", "INFO")
    used_clusters = {m["cluster"] for m in mains}
    rest = [c for c in clean if c not in mains]
    tails = _pick_diverse(rest, 6, used_clusters=used_clusters, avoid_cats={m["cat"] for m in mains},
                          verse_counts=verse_counts, used_anchors=used_anchors, cats=cat_counts)
    if len(tails) < 6:
        # 마지막 빈자리 채우기 — 예전엔 여기서 남은 걸 아무거나 집어넣어 카테고리 상한이
        # 통째로 무력화됐다(2026-07-20 실측: 12회 중 6회에서 상한 2인데 정확히 3개가 됨.
        # 상한이 6번째를 막으면 _pick_diverse가 5개만 돌려주고, 이 줄이 1개를 더 얹었다).
        # 이제 상한을 지키는 후보를 먼저 쓰고, 그래도 모자랄 때만 넘긴다.
        left = [c for c in rest if c not in tails]
        left.sort(key=lambda c: (cat_counts[c["cat"]] >= _cat_cap(c["cat"]),
                                 0 if c["cat"] in _CAT_SAFE else 1,
                                 cat_counts[c["cat"]]))
        for c in left[: 6 - len(tails)]:
            tails.append(c)
            cat_counts[c["cat"]] += 1

    # 느슨한 짝짓기: (꼬리,메인) 쌍을 연관성 높은 순으로 배치, 메인당 최대 2개
    pairs = sorted(((-_relatedness(t, mains[mi]), ti, mi) for ti, t in enumerate(tails) for mi in range(len(mains))))
    assign = [[] for _ in mains]
    done = set()
    for negrel, ti, mi in pairs:
        if ti in done or len(assign[mi]) >= 2:
            continue
        assign[mi].append(tails[ti])
        done.add(ti)

    tree, rid = [], iter(_ROLE_IDS)
    for mi, m in enumerate(mains):
        m["sel"] = True
        node = {"role_id": next(rid), "question": m["q"], "category": m["cat"],
                "topic": m["topic"], "link": m.get("link", ""),
                # anchor를 여기서 버리면 답변 단계가 '이 질문이 어느 관주에서 나왔는지'를
                # 모른다 — 전날형이 link 없이 오늘 본문 안에서만 맴돌던 것(0804)과 같은
                # 구멍이 관주형에 남아 있었다. 8/11 실측: 관주 2개 다 구절을 안 밝혔다.
                "anchor": m.get("anchor", ""), "anchor_type": m.get("anchor_type", "본문"),
                "follow_ups": []}
        for t in assign[mi]:
            t["sel"] = True
            node["follow_ups"].append({"role_id": next(rid), "question": t["q"],
                                       "category": t["cat"], "topic": t["topic"],
                                       "link": t.get("link", ""),
                                       "anchor": t.get("anchor", ""),
                                       "anchor_type": t.get("anchor_type", "본문")})
        tree.append(node)
    picked_all = mains + [t for row in assign for t in row]
    if log:
        cov = sorted({n["category"] for n in fp._iter_all(tree)})
        nclust = len({c["cluster"] for c in picked_all})
        vc = Counter(_vslot(c) for c in picked_all)
        piled = {v: k for v, k in vc.items() if k > 1}
        log(f"  [simple] 다양성 조합 → 카테고리 {len(cov)}개 {cov} · 서로 다른 지식묶음 {nclust}/9", "INFO")
        log(f"  [simple] 자리 배치 → 서로 다른 절 {len(vc)}/9"
            + (f" · 겹친 절 {piled}" if piled else " · 절 겹침 없음"), "INFO")
    return tree


def _cand_dump(pool):
    """후보 전체를 판정·선택여부·지식묶음·출처 기록와 함께 기록."""
    return [{"question": c["q"], "category": c["cat"], "topic": c["topic"], "verdict": c["verdict"],
             "cluster": c["cluster"], "was_main": c["was_main"], "selected": c["sel"],
             "verse": c["verse"], "anchor": c["anchor"], "anchor_ok": c["anchor_ok"],
             "anchor_type": c.get("anchor_type", "본문"), "gist": c.get("gist", ""),
             "hist_dup": c.get("hist_dup", ""),
             "from_qfix": c.get("from_qfix", False)} for c in pool]


# ===== 최종 9개 잔여 문제 수집 (코드 체1·체2 + 판정 잔여) =====
def _residual_problems(tree, history, role_verdicts):
    problems = {}
    seen = []
    for node in fp._iter_all(tree):
        rid = node["role_id"]
        q = node.get("question", "")
        topic = node.get("topic") or q
        reasons = []
        d = _hist_dup(q, topic, history)
        if d:
            reasons.append(f"지난질문 중복({d})")
        if any(_dup_same_day(q, topic, pq, pt) for pq, pt in seen):
            reasons.append("당일 서로 중복")
        v = role_verdicts.get(rid, _GOOD)
        if v != _GOOD:
            reasons.append(v)
        if reasons:
            problems[rid] = "; ".join(reasons)
        seen.append((q, topic))
    return problems


# ===== 걸린 질문 재선택: 후보 풀의 여유분에서 꺼내 쓴다 (GPT 호출 0회) =====
def _refill_from_pool(tree, pool, problems, history, log=None):
    """걸린 질문을 '아직 안 쓴 검증된 후보'로 갈아끼운다. 실패하면 _qfix(GPT)로 넘어간다.

    모델에게 새로 쓰게 하면 그 질문엔 verse·anchor가 없어 절 배치 보호를 통째로 못 받는다
    (2026-07-15 실측: 9개 중 7개가 그렇게 교체돼 출처 기록이 2개만 남았고, 그날 유일한 겹침이
    바로 교체된 질문 둘 사이에서 났다). 풀에 남은 여유분은 이미 판정·출처 기록 검증을 통과한
    것들이라 꺼내 쓰면 그 구멍이 애초에 안 생기고, 값도 이미 치렀다."""
    by_q = {c["q"]: c for c in pool}
    nodes = {n["role_id"]: n for n in fp._iter_all(tree)}

    def _slot_of(node):
        return by_q.get(node["question"])

    # 자리 현황은 '지금 9개 슬롯 전부' 기준으로 센다. 못 채운 슬롯은 원래 질문이 남으므로
    # 그 절도 여전히 점유 중이다 — 이걸 빼고 세면 그 절에 또 얹혀 3개가 될 수 있다.
    cur_v = Counter()
    cur_cl, cur_a = set(), set()
    for n in nodes.values():
        c = _slot_of(n)
        if c:
            cur_v[_vslot(c)] += 1
            cur_cl.add(c["cluster"])
            cur_a.add(_anchor_key(c))
    cats = Counter(n.get("category", "") for n in nodes.values())
    spares = [c for c in pool if not c["sel"] and c["verdict"] == _GOOD and c["anchor_ok"]
              and not c.get("hist_dup")]
    filled = []
    for rid in list(problems):
        node = nodes.get(rid)
        if node is None:
            continue
        old = _slot_of(node)
        if old:  # 이 슬롯을 잠시 비운다 — 자기 절을 자기가 막으면 안 된다
            cur_v[_vslot(old)] -= 1
            cur_cl.discard(old["cluster"])
            cur_a.discard(_anchor_key(old))
            cats[old["cat"]] -= 1
        others = [n for r, n in nodes.items() if r != rid]
        elig = [c for c in spares
                if cur_v[_vslot(c)] == 0 and c["cluster"] not in cur_cl
                and _anchor_key(c) not in cur_a
                and not any(_dup_same_day(c["q"], c["topic"], k["question"], k.get("topic") or "")
                            for k in others)]
        if not elig:  # 재고 없음 → 원상복구하고 _qfix에 넘긴다
            if old:
                cur_v[_vslot(old)] += 1
                cur_cl.add(old["cluster"])
                cur_a.add(_anchor_key(old))
                cats[old["cat"]] += 1
            continue
        c = min(elig, key=lambda c: (cats[c["cat"]], 0 if c["was_main"] else 1))
        if old:
            old["sel"] = False
        c["sel"] = True
        if log:
            log(f"  [simple] 재선택 {rid}: '{node['question'][:14]}…' → "
                f"'{c['q'][:14]}…' ({c['verse']}절·{c['anchor'][:8]})", "INFO")
        node["question"], node["category"], node["topic"] = c["q"], c["cat"], c["topic"]
        # 질문을 갈아끼웠으면 근거도 같이 간다 — 안 바꾸면 답변이 옛 질문의 관주를 인용한다.
        node["anchor"], node["anchor_type"] = c.get("anchor", ""), c.get("anchor_type", "본문")
        spares.remove(c)
        cur_v[_vslot(c)] += 1
        cur_cl.add(c["cluster"])
        cur_a.add(_anchor_key(c))
        cats[c["cat"]] += 1
        filled.append(rid)
    return tree, filled


# ===== 걸린 질문 교체 (mini) — 재고가 바닥났을 때만 =====
def _qfix(chat, qt, kb, deep5, tree, problems, history, total_cost,
          vmap=None, xmap=None, pool=None, log=None, kbmap=None):
    """걸린 질문을 모델이 새로 쓴다. 교체 질문에도 출처 기록을 요구하고 코드가 검증한다.

    왜 필요한가(2026-07-20 실측, 12회 108개): 교체 질문은 전체의 7%인데 겹침쌍의 29%에
    꼈다 — 약 4배 위험했다. 원인은 단순하다. 생성 단계에만 출처 기록을 붙이고 교체 단계는
    옛 코드 그대로 둬서, 교체 질문은 자리 배정도 검증도 전혀 못 받았다. 가장 심한 겹침
    (0.92)이 교체끼리 만든 것이었다 — '모압 사람을 줄로 잰 방식의 의미' ↔ '…의 문화적 배경'.
    검증에 실패하면 교체를 버리고 원래 질문을 유지한다(지어낸 근거를 들이느니 낫다)."""
    nodes = {n["role_id"]: n for n in fp._iter_all(tree)}
    targets = [{"role_id": rid, "기존_질문": nodes[rid]["question"], "문제": r}
               for rid, r in problems.items() if rid in nodes]
    if not targets:
        return tree
    avoid = [n["question"] for n in fp._iter_all(tree) if n["role_id"] not in problems]
    avoid += [h.get("question", "") for h in history]
    # 다른 질문이 이미 차지한 자리 — 모델에게 알려주고, 코드로도 막는다.
    by_q = {c["q"]: c for c in (pool or [])}
    used = set()
    taken_desc = []
    for rid, n in nodes.items():
        if rid in problems:
            continue
        c = by_q.get(n["question"])
        if c and _anchor_key(c):
            used.add(_anchor_key(c))
            taken_desc.append(_slot_desc(c))
    payload = {"본문_참조": qt.get("scripture_ref", ""), "본문_내용": fp._body_text(qt),
               "지식": _kb_numbered(kb), "관주_연결": _xref_text(qt), "이미_다룬_5단": deep5,
               "고쳐야_할_슬롯": targets, "피해야_할_질문": avoid, "이미_쓴_자리": taken_desc}
    rids = [t["role_id"] for t in targets]
    try:
        data, cost = chat(QFIX_MODEL, _qfix_system(), payload, "followup_qfix",
                          _qfix_schema(rids), 0.7, 2500)
        fp._add_cost(total_cost, cost)
    except Exception as e:
        if log:
            log(f"  [simple] 질문 교체 실패 — 원본 유지: {e}", "WARN")
        return tree
    for item in data.get("fixes", []):
        rid = item.get("role_id")
        if rid not in nodes or not item.get("question"):
            continue
        v, a = item.get("verse"), item.get("anchor", "")
        at = item.get("anchor_type", "본문")
        ok = _anchor_ok(v, a, vmap or {}, at, xmap, kbmap)
        key = (v, at, fp._norm(a)) if ok else None
        if not ok:
            if log:
                log(f"  [simple] 교체 거부 {rid}: 출처 기록 검증 실패({v}절 {at} '{a[:12]}') — 원본 유지", "WARN")
            continue
        if key in used:
            if log:
                log(f"  [simple] 교체 거부 {rid}: 이미 쓴 자리({v}절 '{a[:12]}') — 원본 유지", "WARN")
            continue
        used.add(key)
        if log:
            log(f"  [simple] 교체 {rid}: '{nodes[rid]['question'][:14]}…' → "
                f"'{item['question'][:14]}…' ({v}절·{a[:8]})", "INFO")
        nodes[rid]["question"] = item["question"]
        nodes[rid]["category"] = _canon_cat(item.get("category", nodes[rid].get("category", "")))
        nodes[rid]["topic"] = item.get("topic", "")
        nodes[rid]["anchor"], nodes[rid]["anchor_type"] = a, at
        if pool is not None:   # 새 질문도 후보 풀에 남겨 측정·보고에 출처가 보이게 한다
            pool.append({"q": item["question"], "cat": nodes[rid]["category"],
                         "topic": nodes[rid]["topic"], "verdict": _GOOD, "cluster": f"qfix_{rid}",
                         "was_main": False, "sel": True, "verse": v, "anchor": a,
                         "anchor_type": at, "anchor_ok": True, "gist": "", "from_qfix": True})
    return tree


def _usable_kb(kb):
    if not kb:
        return None
    return kb if any(isinstance(k, str) and k.isdigit() for k in kb.keys()) else None


# ===== 오케스트레이션 =====
def run_simple(chat, qt, kb, deep5, *, history=None, mode="none", log=None, recent=None,
               embed=None, today="", recent_qs=None):
    history = history or []
    today = today or qt.get("date", "")
    total_cost = dict(_ZERO_COST)
    kb_use = _usable_kb(kb)

    # ① 후보 생성
    # 카테고리 4갈래를 각각 전용 호출로 뽑는다 — 본체 하나에 다 맡기면 '왜 그랬나'(해석형)로
    # 쏠려서 나머지 갈래가 0개가 된다. 배경지식형은 0804에 함수만 만들고 여기 배선을 빠뜨려
    # 4일 내내 한 번도 안 돌았다(그날 후보가 9개뿐이었던 주된 이유).
    branches = _gen_candidates(chat, qt, kb_use, deep5, history, total_cost, log=log, recent=recent)
    gwan = _gen_gwanju(chat, qt, history, total_cost, log=log)
    prev = _gen_prevday(chat, qt, recent, history, total_cost, log=log)
    back = _gen_background(chat, qt, kb_use, history, total_cost, log=log) if kb_use else []
    calls = 2 + (1 if recent else 0) + (1 if kb_use else 0)
    for extra in (gwan, prev, back):
        if not extra:
            continue
        base = max((bb["idx"] for bb in branches), default=-1) + 1
        branches = branches + [{"idx": base + i, "main": c, "tails": []} for i, c in enumerate(extra)]
    # ② 판정 (본문·5단 재진술 + 메인포함) + 답 겹치는 지식묶음 그룹핑
    verdicts, clusters, gists = _judge(chat, qt, deep5, branches, total_cost, log=log)
    calls += 1
    if log:
        vc = Counter(verdicts.values())
        log(f"  [simple/{mode}] 후보 {len(branches)}개 판정: {dict(vc)} · 답겹침 묶음 {len(set(clusters.values()))}개", "INFO")
    # ③ 묶음 해체 → 자리(절·anchor) + 답 겹침 + 카테고리 다양하게 메인3·꼬리6 선택
    vmap, xmap, kbmap = _verse_map(qt), _xref_map(qt), _kb_map(kb_use)
    # 본문에 근거를 둔 후보는 판정 전에 근거를 본문 글자로 맞춰 둔다 — 어긋났다고 버리면
    # '옮겨 적다 한 글자 틀린' 멀쩡한 질문이 후순위로 밀린다(0804: 하루 1~6건).
    _verses = [(v["number"], v["text"]) for v in qt.get("verses", [])]
    for _b in branches:
        for _c in [_b["main"]] + list(_b.get("tails") or []):
            if _c.get("anchor_type", "본문") in ("본문", "전날"):
                _repair_anchor(_c, _verses)
    pool = _flatten_pool(branches, verdicts, clusters, vmap, xmap, gists, kbmap)
    bad = [c for c in pool if not c["anchor_ok"]]
    if log and bad:
        log(f"  [simple/{mode}] 출처 기록 검증 실패 {len(bad)}/{len(pool)}건(원자료에 없는 anchor → 후순위): "
            + "; ".join(_slot_desc(c, 12) for c in bad[:5]), "WARN")
    pool = _gate_clusters(pool, log=log)

    # 지난 질문 대조 — 최근 3일치 답변과 '뜻'으로 비교(글자 잣대는 적중 0/17이라 폐기)
    hist_index = _hist_index(history, embed, today, log=log)
    _CORE_VECS.clear()
    cores = sorted({c.get("gist", "") for c in pool if c.get("gist")})
    if cores and hist_index and embed is not None:
        try:
            for text, vec in zip(cores, embed([_core_shape(t) for t in cores])):
                if vec:
                    _CORE_VECS[text] = vec
        except Exception as e:
            if log:
                log(f"  [지난중복] gist 임베딩 실패 — 대조 건너뜀: {str(e)[:70]}", "WARN")
    hits = 0
    for c in pool:
        d = _hist_dup_embed(c.get("gist", ""), hist_index)
        c["hist_dup"] = d or ""
        if d:
            hits += 1
    if log:
        log(f"  [지난중복] 최근 {_HIST_WINDOW_DAYS}일치 {len(hist_index)}개와 대조 → "
            f"후보 {len(pool)}개 중 {hits}개가 지난 답과 겹침(유사도 {_HIST_SIM}+)", "INFO")  # 의미↔영향 코드 하드게이트로 지식묶음 확정
    tree = _assemble_diverse(pool, history, log=log)
    role_v = {c["q"]: c["verdict"] for c in pool}  # 질문문→판정 (잔여 검사용)

    # 선택된 9개의 잔여 문제(체1 지난질문 + 체2 표면 + 판정 잔여)만 교체
    problems = _residual_problems(tree, history, {n["role_id"]: role_v.get(n["question"], _GOOD)
                                                  for n in fp._iter_all(tree)})
    initial_problems = dict(problems)
    if log and problems:
        log(f"  [simple/{mode}] 선택 9개 잔여 문제 {len(problems)}건: "
            + "; ".join(f"{r}({v[:20]})" for r, v in problems.items()), "WARN")

    def _recheck():
        # 판정 결과까지 같이 본다. role_v 없이 부르면 코드 체1·2만 재검사해서,
        # 재선택으로 못 채운 슬롯의 '재진술' 문제가 조용히 사라진다(→ _qfix로 안 넘어간다).
        return _residual_problems(tree, history,
                                  {n["role_id"]: role_v.get(n["question"], _GOOD)
                                   for n in fp._iter_all(tree)})

    # ①먼저 후보 풀의 여유분에서 꺼내 쓴다(공짜·출처 기록 보장). ②재고가 없을 때만 _qfix(GPT).
    refilled = []
    if problems:
        tree, refilled = _refill_from_pool(tree, pool, problems, history, log=log)
        if refilled:
            problems = _recheck()
            if log:
                log(f"  [simple/{mode}] 재선택으로 {len(refilled)}건 해결(GPT 0회) · "
                    f"남은 문제 {len(problems)}건", "INFO")
    fix_rounds = 0
    while problems and fix_rounds < 2:
        tree = _qfix(chat, qt, kb_use, deep5, tree, problems, history, total_cost,
                     vmap=vmap, xmap=xmap, pool=pool, log=log, kbmap=kbmap)
        calls += 1
        fix_rounds += 1
        problems = _residual_problems(tree, history, {})  # 교체 후엔 코드 체1·2만 재검(판정 재호출 안 함)
    residual = problems
    if residual and log:
        log(f"  [simple/{mode}] 최종 미해결 {len(residual)}건(원본 유지): {list(residual)}", "ERR")

    # ④ 답변 1회 (4o, 검증+재시도)
    answers = fp.write_answers(chat, qt, kb_use, deep5, tree, total_cost,
                               recent=recent, recent_qs=recent_qs)
    fp._apply_answers(tree, answers)
    calls += 1

    items = [{"question": m["question"], "answer": m["answer"],
              "follow_ups": [{"question": t["question"], "answer": t["answer"]} for t in m["follow_ups"]]}
             for m in tree]
    covered = sorted({n["category"] for n in fp._iter_all(tree)})
    sel_clusters = [c["cluster"] for c in pool if c["sel"]]
    meta = {
        "generation_method": f"simple5_distinct_{mode}",
        "gpt_calls": calls, "fix_rounds": fix_rounds,
        "refilled_from_pool": len(refilled),   # 공짜로 갈아끼운 건수(출처 기록 유지됨)
        "candidate_count": sum(1 + len(b["tails"]) for b in branches),
        "judge_verdicts": dict(Counter(verdicts.values())),
        "answer_group_count": len(set(clusters.values())),
        "distinct_knowledge_in_final": len(set(sel_clusters)),
        # 자리 지표 — 모델 판단이 아니라 코드가 본문과 대조해 센 값이라 지표 중 유일하게 못 속인다.
        "distinct_verses_in_final": len({_vslot(c) for c in pool if c["sel"]}),
        "verse_pileup": {str(v): n for v, n in Counter(_vslot(c) for c in pool if c["sel"]).items() if n > 1},
        "anchor_verify_failed": sum(1 for c in pool if not c["anchor_ok"]),
        "passage_verse_count": len(vmap),
        "covered_categories": covered,
        "candidates": _cand_dump(pool),
        "kb_coverage": fp.count_kb_coverage(kb),
        "initial_problems": initial_problems, "residual_unresolved": list(residual),
        "category_map": [{"role_id": m["role_id"], "category": m.get("category"),
                          "topic": m.get("topic"), "question": m["question"]}
                         for m in fp._iter_all(tree)],
    }
    return items, total_cost, meta


# ===== 베스트-of-N: 답변 임베딩 겹침이 제일 적은 세트를 자동 선택 =====
# 배경: 파이프라인 안의 dedup은 '자리(절·anchor)' 기준이라 '의미적 중복'(절은 다른데 답이
#   수렴)을 통과시킨다. 신뢰할 잣대는 '답변 전체 임베딩'뿐(질문·gist 임베딩은 2026-07 실측
#   기각). 그래서 run_simple을 N번 돌려 각 세트의 답변 겹침을 재고 제일 깨끗한 세트를 고른다.
#   온도 0.75·seed 없음으로 '어떤 날 겹침 8건' 참사가 나던 걸 원천 차단.
#   실측(2026-07-30): 5일(6/20·7/21·7/14·7/24·7/16) 전부 옛 단발 대비 개선(3→2·3→0·2→0·4→3·4→1).
_SIM_THRESHOLD = 0.75  # 답변 임베딩 코사인 — 이 이상이면 '겹침 의심 쌍' (오프라인 잣대와 동일 기준)


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _overlap_score(items, embed):
    """items의 답변 9개(메인3+꼬리6)를 임베딩해 (겹침쌍 수, 최고유사도) 반환 — 낮을수록 좋음.
    답변이 없거나 embed 실패 시 (None, None)."""
    answers = []
    for m in items:
        answers.append(m.get("answer", ""))
        for t in m.get("follow_ups", []):
            answers.append(t.get("answer", ""))
    answers = [a for a in answers if a]
    if not answers or embed is None:
        return None, None
    try:
        vecs = embed(answers)
    except Exception:
        return None, None
    flags, mx = 0, 0.0
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            s = _cosine(vecs[i], vecs[j])
            if s > mx:
                mx = s
            if s >= _SIM_THRESHOLD:
                flags += 1
    return flags, round(mx, 4)


# ===== 임베딩 관문: 답이 겹치는 질문은 빼고 '정직한 가변 개수'로 =====
# 배경(2026-08-03 실측): 9개를 억지로 채우는 게 문제였다. 객관 잣대(답변 임베딩 코사인
#   ≥0.75)로 9일을 재보니 7일은 9개에서 이미 깨끗했고, 겹침은 '압살롬 도망'처럼 본문이
#   극단적으로 단일주제인 날에만 몰렸다. 그런 날엔 9개를 채우는 순간 같은 답이 여러 번
#   나온다. 그래서 답이 겹치는 쌍은 하나만 남기고 빼서, 그날 본문이 정직하게 감당하는
#   개수(보통 9, 가끔 5~8)만 내보낸다. 개수를 줄이는 게 손해가 아니라 중복을 없애는 것.
# best-of-N과의 관계: 관문은 best-of-N '뒤'에 선다. 먼저 N판 중 제일 깨끗한 판을 고르고
#   (조기 종료 그대로 → 비용 불변), 그러고도 남은 겹침만 관문이 자른다. 순서를 뒤집어
#   run_simple 안에 넣으면 매 판이 '겹침 0'으로 보고돼 항상 1판에서 멈춘다(=best-of-N 무력화).
_GATE_KEEP_GWANJU_FIRST = True   # 한 그룹에서 살릴 하나를 고를 때 검증된 관주형을 우선한다


def _greedy_keep(vecs, order, thr):
    """'이미 살아남은 것'과만 비교해 자른다 — 연쇄 병합을 없앤 방식.

    union-find(단일 연결)는 A~B가 겹치고 B~C가 겹치면 A와 C가 안 겹쳐도 셋을 한 덩어리로
    묶는다. 0803에 그 때문에 8개가 한 덩어리가 되어 질문이 9개→2개로 무너졌고, 그래서
    자르기를 통째로 꺼 뒀다. 순차 방식은 그 일이 구조적으로 일어나지 않는다
    (기록된 겹침으로 모의: union-find 5·5·8·8개 → 순차 5·6·8·8개).

    order = 살릴 우선순위(관주형 → 메인 → 먼저 나온 것). 반환: (남길 인덱스, {버릴것: (대신남긴것, 유사도)})
    """
    keep, dropped = [], {}
    for k in order:
        hit = None
        for w in keep:
            sim = _cosine(vecs[k], vecs[w])
            if sim >= thr and (hit is None or sim > hit[1]):
                hit = (w, sim)
        if hit is None:
            keep.append(k)
        else:
            dropped[k] = hit
    return keep, dropped


def _uf_groups(pairs, n):
    """겹침 쌍을 union-find로 묶어 그룹 목록(각 그룹=인덱스 오름차순)으로 반환."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return [sorted(v) for v in groups.values()]


def _flat_nodes(items):
    """중첩 구조(메인3+꼬리6)를 (메인idx, 꼬리idx, 질문, 답변) 평탄 목록으로. 꼬리idx=-1이면 메인."""
    nodes = []
    for i, m in enumerate(items):
        nodes.append((i, -1, m.get("question", ""), m.get("answer", "")))
        for j, t in enumerate(m.get("follow_ups") or []):
            nodes.append((i, j, t.get("question", ""), t.get("answer", "")))
    return nodes


# 2026-08-04 사장님 결정 — 관문은 '자르지 않고 기록만' 한다.
#
# 왜: 8/03 실측에서 9개 중 7개가 잘려 최종 2개가 됐다. 원인은 '연쇄 병합'이다.
#   관문은 겹치는 쌍을 union-find로 줄줄이 이어 붙이는데(단일 연결),
#   A~B가 겹치고 B~C가 겹치면 A~C가 안 겹쳐도 A·B·C가 한 덩어리가 된다.
#   그날 걸린 쌍 10개가 이어져 8개가 한 덩어리가 됐고, 덩어리당 1개만 남기니 7개가 사라졌다.
#   병거(1절)와 입맞춤(5절)은 서로 안 겹쳤을 텐데 중간에 낀 것들 때문에 같이 묶였다.
# 그래서 자르는 동작만 끄고 판정 결과는 meta['embed_gate']에 그대로 남긴다 —
# 무엇이 왜 겹쳤는지 계속 볼 수 있어야 연쇄 병합을 고칠 때 근거가 된다.
# 중복 제거는 그 앞 단계(판정기의 answer_groups)가 이미 맡고 있다.
GATE_CUT = True


def apply_embed_gate(items, meta, embed, *, log=None):
    """답변 임베딩이 ≥0.75로 겹치는 질문을 '그룹당 1개'만 남기고 빼낸다.
    GATE_CUT=False면 실제로 빼지 않고 무엇이 걸렸는지 기록만 남긴다.

    - 살릴 하나 고르는 우선순위: ①검증된 관주형(배경지식형) ②메인 ③먼저 나온 것.
      0.75는 '선별 그물이지 판결'이 아니라 오탐이 있다 → 가치 큰 관주형을 우선 살리는 보수적 선택.
    - 메인이 잘리면 그 가지에서 살아남은 첫 꼬리를 메인으로 승격하고 나머지 꼬리를 그 밑에 붙인다
      (겹치지도 않은 멀쩡한 꼬리까지 부모와 함께 버리지 않으려고). 가지가 통째로 비면 그 가지는 뺀다.
    - 답변이 비었거나 임베딩이 실패하면 아무것도 안 자르고 원본을 그대로 돌려준다(안전 우선).
    반환: (items, meta) — meta['embed_gate']에 무엇을 왜 뺐는지 기록.
    """
    nodes = _flat_nodes(items)
    answers = [a for _i, _j, _q, a in nodes]
    if not items or not answers or not all(answers) or embed is None:
        return items, meta
    try:
        vecs = embed(answers)
    except Exception as e:
        if log:
            log(f"  [관문] 임베딩 실패 — 관문 건너뜀(원본 {len(nodes)}개 유지): {str(e)[:70]}", "WARN")
        return items, meta

    # 검증된 관주형 표시: meta['candidates']의 anchor_type=='관주' + anchor_ok(원자료 대조 통과)
    gwanju_q = {c["question"] for c in (meta.get("candidates") or [])
                if c.get("anchor_type") == "관주" and c.get("anchor_ok")}
    is_gwanju = [nodes[k][2] in gwanju_q for k in range(len(nodes))]

    flagged, max_sim = [], 0.0
    for a in range(len(vecs)):
        for b in range(a + 1, len(vecs)):
            s = _cosine(vecs[a], vecs[b])
            max_sim = max(max_sim, s)   # 걸린 쌍만이 아니라 '전체 쌍'의 최고치 — 안 걸린 날도 여유를 보려고
            if s >= _SIM_THRESHOLD:
                flagged.append((a, b, round(s, 4)))

    # 살릴 우선순위: ①검증된 관주형 ②메인(꼬리idx==-1) ③먼저 나온 것
    order = sorted(range(len(nodes)),
                   key=lambda k: (not (_GATE_KEEP_GWANJU_FIRST and is_gwanju[k]),
                                  nodes[k][1] != -1, k))
    keep_list, drop_map = _greedy_keep(vecs, order, _SIM_THRESHOLD)
    keep = set(keep_list)
    dropped = [{"question": nodes[k][2], "kept_instead": nodes[w][2],
                "sim": round(sim, 4), "was_main": nodes[k][1] == -1}
               for k, (w, sim) in drop_map.items()]

    if not GATE_CUT:
        # 기록만 하고 원본을 그대로 돌려준다 — 연쇄 병합 때문에 과하게 잘린다(위 주석 참고).
        meta = dict(meta)
        meta["embed_gate"] = {
            "cut_enabled": False, "threshold": _SIM_THRESHOLD, "before_count": len(nodes),
            "final_count": len(nodes), "flagged_pairs": len(flagged),
            "max_sim": round(max_sim, 4),
            "would_drop": [{"question": nodes[k][2], "kept_instead": nodes[w][2]}
                           for group in _uf_groups([(a, b) for a, b, _s in flagged], len(nodes))
                           if len(group) > 1
                           for w in [min(group, key=lambda k: (not (_GATE_KEEP_GWANJU_FIRST and is_gwanju[k]),
                                                               nodes[k][1] != -1, k))]
                           for k in group if k != w],
            "flagged_detail": [{"a": nodes[a][2], "b": nodes[b][2], "sim": s} for a, b, s in flagged],
        }
        if log:
            log(f"  [관문] 겹침 {len(flagged)}쌍 감지 · 최고 {round(max_sim,3)} — "
                f"자르지 않고 기록만 (연쇄 병합 문제로 중단, 사장님 결정 0804)", "INFO")
        return items, meta

    # 살아남은 것만으로 메인+꼬리 구조 재조립 (메인이 잘리면 첫 생존 꼬리가 승격)
    new_items, promoted = [], []
    for i, m in enumerate(items):
        branch = [k for k in range(len(nodes)) if nodes[k][0] == i and k in keep]
        if not branch:
            continue
        head, tails = branch[0], branch[1:]
        if nodes[head][1] != -1:      # 메인이 잘려 꼬리가 올라온 경우
            promoted.append({"from": nodes[head][2], "replaced_main": m.get("question", "")})
        src = (lambda k: m if nodes[k][1] == -1 else (m.get("follow_ups") or [])[nodes[k][1]])
        new_items.append({
            "question": src(head).get("question", ""), "answer": src(head).get("answer", ""),
            "follow_ups": [{"question": src(k).get("question", ""),
                            "answer": src(k).get("answer", "")} for k in tails],
        })

    meta = dict(meta)
    meta["embed_gate"] = {
        "threshold": _SIM_THRESHOLD,
        "before_count": len(nodes),
        "final_count": len(keep),
        "dropped_by_embed": len(nodes) - len(keep),
        "flagged_pairs": len(flagged),
        "max_sim": round(max_sim, 4),
        "mains_after": len(new_items),
        "gwanju_kept": sum(1 for k in keep if is_gwanju[k]),
        "dropped": dropped,
        "promoted": promoted,
        # 관문에 들어가기 '전' 상태를 통째로 남긴다 — 잘린 질문의 답변까지 있어야 사람이
        # "이게 진짜 중복인가"를 나중에 직접 판정할 수 있다(2026-08-03: 안 남겨서 못 봤다).
        "before_nodes": [{"q": nodes[k][2], "a": nodes[k][3], "kept": k in keep,
                          "gwanju": is_gwanju[k],
                          "main_idx": nodes[k][0], "tail_idx": nodes[k][1]}
                         for k in range(len(nodes))],
        # 문턱 근처 쌍도 남긴다(0.60↑) — 문턱을 올릴지 내릴지 판단할 재료
        "pair_sims": [[a, b, round(_cosine(vecs[a], vecs[b]), 4)]
                      for a in range(len(vecs)) for b in range(a + 1, len(vecs))
                      if _cosine(vecs[a], vecs[b]) >= 0.60],
    }
    if log:
        if dropped:
            log(f"  [관문] 답 겹침 {len(flagged)}쌍 → {len(nodes)}개 중 {len(dropped)}개 뺌 "
                f"(최종 {len(keep)}개 · 메인 {len(new_items)}가지"
                + (f" · 꼬리 승격 {len(promoted)}건" if promoted else "") + ")", "OK")
            for d in dropped:
                log(f"     뜻 {d['sim']} 겹침으로 뺌: {d['question'][:40]} (남긴 것: {d['kept_instead'][:40]})", "INFO")
        else:
            log(f"  [관문] 답 겹침 없음 — {len(nodes)}개 전부 유지", "OK")
    return new_items, meta


_PRIORITY_TYPES = ("관주", "전날")   # 오늘 본문 밖을 근거로 삼아 소재가 구조적으로 안 겹치는 종류
_PRIORITY_TARGET = 2                # 이만큼 다 들어온 판이면 더 안 뽑아도 된다


def _priority_kinds(items, meta):
    """최종 9개에 살아남은 우선 질문(관주형·전날형)의 '종류'를 모은다.
    meta['candidates']에 검증 통과 표시가 있는 것만 인정한다 — 지어낸 근거는 세지 않는다."""
    ok = {}
    for c in (meta.get("candidates") or []):
        if c.get("anchor_type") in _PRIORITY_TYPES and c.get("anchor_ok"):
            ok[c.get("question", "")] = c["anchor_type"]
    kinds = set()
    for m in items or []:
        for node in [m] + list(m.get("follow_ups") or []):
            t = ok.get(node.get("question", ""))
            if t:
                kinds.add(t)
    return kinds


def run_best_of_n(chat, qt, kb, deep5, *, history=None, mode="none", log=None,
                  n=3, embed=None, target=1, recent=None, recent_qs=None):
    """run_simple을 최대 n번 실행해 '답변 임베딩 겹침'이 제일 적은 세트를 고른다.
    - embed: 문장 리스트→벡터 리스트 함수(주입). None이면 best-of-N 끄고 run_simple 1회(기존 동작).
    - target: 겹침쌍이 이 값 이하인 세트가 나오면 조기 종료(비용 절약). 기본 1 — 관문이 생긴
      뒤로는 겹침 1건은 어차피 관문이 지우므로 0을 고집할 이유가 없다. 0이면 조기 종료가
      거의 안 걸려 매일 n판을 다 돌린다(2026-08-03 실측 3일: 9판 전부 소진, 하루 471원).
      1로 풀면 같은 3일이 6판으로 줄고 최종 결과는 세 날 모두 동일했다.
    - 한 run이 실패하면(예: 답변 role_id 불일치) 그 판만 건너뛰고 다음 판 사용.
    - 고른 세트에 마지막으로 임베딩 관문(apply_embed_gate)을 통과시킨다 → 그러고도 남은
      겹침만 잘려 개수가 가변(보통 9, 겹치는 날만 5~8)이 된다.
    반환: (items, 누적_cost, meta) — run_simple과 동일 시그니처. meta['best_of_n']에 선택 기록.
    """
    if embed is None:   # 임베딩이 없으면 판 고르기도 관문도 못 한다 → 옛 단발 동작 그대로
        return run_simple(chat, qt, kb, deep5, history=history, mode=mode, log=log, recent=recent, recent_qs=recent_qs,
                          embed=embed, today=qt.get('date', ''))
    if n <= 1:          # 판 고르기만 끄고 관문은 살린다
        items, cost, meta = run_simple(chat, qt, kb, deep5, history=history, mode=mode, log=log, recent=recent, recent_qs=recent_qs,
                          embed=embed, today=qt.get('date', ''))
        items, meta = apply_embed_gate(items, meta, embed, log=log)
        return items, cost, meta

    best = None  # (score, items, cost, meta, flags, mx, run_idx)
    attempts = []
    acc_cost = dict(_ZERO_COST)
    last_err = None
    # 그날 재료로 만들 수 있는 우선 질문 종류 수 — 관주 자료가 없으면 관주형은 애초에 못 만든다.
    possible_kinds = (1 if _xref_text(qt) else 0) + (1 if recent else 0)
    for r in range(1, n + 1):
        try:
            items, cost, meta = run_simple(chat, qt, kb, deep5, history=history, mode=mode, log=log, recent=recent, recent_qs=recent_qs,
                          embed=embed, today=qt.get('date', ''))
        except Exception as e:
            last_err = e
            if log:
                log(f"  [best-of-{n}] run{r} 실패(제외): {str(e)[:70]}", "WARN")
            continue
        for k in list(acc_cost):
            acc_cost[k] = round(acc_cost.get(k, 0) + cost.get(k, 0), 6)
        flags, mx = _overlap_score(items, embed)
        # 우선 질문(관주형·전날형)이 몇 종류 살아남았나 — 겹침만 보고 고르면 관주가 든 판이
        # '겹침 1건 많다'는 이유로 탈락한다(2026-07-30 실측: 최종 관주 0개). 우선 질문은
        # 소재가 구조적으로 안 겹치는 고급 재료라, 겹침 1~2건과 바꿀 값이 있다.
        kinds = _priority_kinds(items, meta)
        attempts.append({"run": r, "flags": flags, "max_sim": mx, "priority_kinds": sorted(kinds)})
        # 정렬 키: ①우선 질문 종류가 많은 판 먼저 ②그다음 겹침 적은 판 ③그다음 최고유사도
        score = (-len(kinds), flags, mx) if flags is not None else (0, 10 ** 6, r)
        if log:
            log(f"  [best-of-{n}] run{r}: 답겹침 {flags if flags is not None else '?'}건 · "
                f"최고 {mx if mx is not None else '?'} · 우선질문 {sorted(kinds) or '없음'}", "INFO")
        if best is None or score < best[0]:
            best = (score, items, cost, meta, flags, mx, r)
        # 조기 종료는 '겹침도 적고 우선 질문도 다 들어온' 판에서만. 겹침만 보고 멈추면
        # 관주·전날이 빠진 판에 안주하게 된다. 단 '다 들어온'의 기준은 그날 재료로 만들 수
        # 있는 만큼이다 — 관주가 없는 날까지 2종류를 요구하면 매일 n판을 다 돌려 비용만 3배 된다.
        want = min(_PRIORITY_TARGET, possible_kinds)
        if flags is not None and flags <= target and len(kinds) >= want:
            if log:
                log(f"  [best-of-{n}] run{r} 목표 달성(겹침 ≤{target} · 우선질문 {sorted(kinds)}) → 조기 종료", "INFO")
            break

    if best is None:
        raise last_err or fp.FollowUpPoolError(f"best-of-{n}: 모든 run 실패")
    _score, items, _cost, meta, flags, mx, run_idx = best
    meta = dict(meta)
    meta["best_of_n"] = {"n": n, "runs_done": len(attempts), "chosen_run": run_idx,
                         "chosen_flags": flags, "chosen_max_sim": mx, "attempts": attempts}
    if log:
        log(f"  [best-of-{n}] {len(attempts)}판 중 run{run_idx} 채택 (답겹침 {flags}건 · 최고 {mx})", "OK")
    # 제일 깨끗한 판에도 남아 있는 겹침만 관문이 자른다 → 정직한 가변 개수
    items, meta = apply_embed_gate(items, meta, embed, log=log)
    return items, acc_cost, meta
