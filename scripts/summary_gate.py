# -*- coding: utf-8 -*-
"""핵심 요약 5줄 저장 전 게이트 — 본문의 이름·사물이 요약에서 빠지거나 바뀌지 않았는지 본다.

왜 필요한가(0805 실측): 요약 프롬프트에 "이름을 빼지 마라"라고 적어 두어도 매번 지켜지지
않는다. 7/01은 '아말렉'도 '왕관과 팔에 있는 고리'도 사라진 채 저장됐고, 그게 뒷날 답변이
'그 왕관이 어디서 났나'를 되짚지 못한 원인이었다. 또 재료를 본문 기준으로 바꾼 뒤에도
'팔에 있는 고리'가 '팔찌'로 바뀌어 나온 적이 있다. 말로 부탁하는 대신 저장 직전에 확인한다.

왜 규칙(정규식)이 아니라 모델인가: 조사를 떼고 희귀도로 이름을 골라내는 방식을 먼저 만들어
돌려봤는데, 7/01에서 '외국인·이틀·목숨·주께'를 실마리로 집고 정작 '아말렉·왕관·시글락'은
놓쳤다. KB와 교차해 보니 이번엔 '고리'가 빠졌다. 한국어에서 이름과 서술어를 규칙으로
가르는 건 이 정도가 한계라, 판정만 값싼 mini에게 맡긴다(하루 1원 안팎). 글은 4o가 쓴다.
"""
from __future__ import annotations

GATE_MODEL = "gpt-4o-mini"

_SYSTEM = """# 이 본문에서 '뒷날이 되짚을 실마리'를 고른다

본문을 준다. 며칠 뒤의 독자가 앞 흐름을 되짚을 때 **없으면 이야기가 끊기는 낱말**만 고른다.

## 고를 것 (많아야 5개)
- 사람·장소의 이름: 아히도벨, 헤브론
- 이야기를 이어 주는 물건·수량: 왕관, 팔에 있는 고리, 병거와 오십 명, 채색옷

## 고르지 않을 것
- 매번 나오는 주인공 이름(그날 이야기의 주어라 어차피 안 빠진다)
- 일반 명사(사람·왕·아들·군사·소식), 서술어, 감정·평가 표현

## 어떻게 적나
**본문에 적힌 글자 그대로** 적는다. 요약문이 그 글자를 그대로 쓸 수 있어야 한다.
'팔에 있는 고리'처럼 긴 것은 이어질 때 쓰는 짧은 형태('고리')로 적는다.

## 출력
`{"실마리": ["...", "..."]}` — 없으면 빈 배열."""


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {"실마리": {"type": "array", "maxItems": 5, "items": {"type": "string"}}},
        "required": ["실마리"],
        "additionalProperties": False,
    }


def key_terms(chat, qt: dict, total_cost: dict | None = None) -> list[str]:
    """그날 본문의 실마리 낱말을 mini에게 고르게 한다(하루 1원 안팎).

    고르는 일만 모델에게 맡기고 '요약에 있나 없나'는 코드가 문자열로 확인한다.
    모델에게 판정까지 맡겼더니 요약에 멀쩡히 있는 '사울·다말'까지 빠졌다고 집어서
    매번 헛되이 다시 부르게 됐다(0805 실측).
    """
    # 절 번호를 떼고 넘긴다. 번호를 붙이면 mini가 '7 사 년 만에'처럼 번호까지 실마리로 집는데,
    # 요약문에 절 번호가 들어갈 리 없으니 그 실마리는 영영 못 채운다 → 매일 헛되이 다시 부름(0805).
    body = "\n".join(v.get("text", "") for v in qt.get("verses", []))
    try:
        data, cost = chat(GATE_MODEL, _SYSTEM, {"본문": body}, "summary_clues", _schema(), 0.0, 200)
    except Exception:
        return []
    if total_cost is not None:
        for k in ("input_tokens", "output_tokens", "total_tokens"):
            total_cost[k] = total_cost.get(k, 0) + cost.get(k, 0)
        for k in ("cost_usd", "cost_krw"):
            total_cost[k] = round(total_cost.get(k, 0) + cost.get(k, 0), 6)
    # 본문에 없는 낱말은 버린다 — mini가 위 예시('병거와 오십 명')를 그대로 옮겨 적은 적이 있다.
    # 없는 걸 실마리로 세면 영영 못 채워서 헛되이 다시 부르게 된다.
    return [s.strip() for s in (data.get("실마리") or [])
            if isinstance(s, str) and s.strip() and s.strip() in body]


def check(lines: list, terms: list) -> list:
    """요약에서 빠진 실마리 — 문자열 확인이라 오탐이 없다."""
    text = " ".join(lines or [])
    return [t for t in terms if t not in text]


def hint(miss: list) -> str:
    """다시 부를 때 덧붙일 지시문."""
    return ("\n\n## 다시 쓴다\n앞선 답이 본문의 실마리를 흘렸다. 아래를 **본문에 적힌 글자 그대로** "
            "살려서 다시 써라. 억지로 다섯 줄에 나눠 넣지 말고, 그 대목을 적는 줄에만 넣어라. "
            "다른 줄은 건드리지 마라.\n- " + "\n- ".join(miss))
