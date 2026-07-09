"""Bible Hub 인터리니어·Strong's 원어 조사 — generate_kb.py 보조 모듈.

유료 웹검색 도구 대신, URL 패턴이 예측 가능한 Bible Hub 페이지를 직접 가져와서
(비용 없음, 순수 HTTP 요청) 절별 히브리어 원문·Strong's 번호·품사를 뽑고,
고유명사 위주로 Strong's 사전 페이지까지 따라가 어원을 가져온다. 이 결과를
generate_kb.py가 GPT 프롬프트에 "실제 조사된 자료"로 끼워 넣는다.

실패해도 조용히 넘어간다(사이트 구조 변경·차단·네트워크 문제) — KB 생성 자체가
막히면 안 되므로, 이 모듈은 항상 "있으면 보탬, 없으면 기존 방식대로" 취급된다.
"""
import time
from bs4 import BeautifulSoup

try:
    import requests
except ImportError:
    requests = None

USER_AGENT = "Mozilla/5.0 (compatible; personal-qt-kb-research/1.0; non-commercial verse study tool)"
REQUEST_TIMEOUT = 12
REQUEST_DELAY = 0.3   # 연속 요청 사이 예의상 딜레이(초)

# 이 프로젝트가 다루는 책만 우선 등록. 필요할 때마다 추가.
BOOK_SLUGS = {
    "사무엘상": "1_samuel",
    "사무엘하": "2_samuel",
    "사사기": "judges",
    "룻기": "ruth",
    "열왕기상": "1_kings",
    "열왕기하": "2_kings",
}


def _get(url: str):
    if requests is None:
        return None
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception:
        return None


def fetch_verse_interlinear(book_slug: str, chapter: int, verse: int) -> list[dict] | None:
    """그 절의 단어별 [{strongs, translit, hebrew, gloss, parsing}, ...]. 절이 없으면 None."""
    html = _get(f"https://biblehub.com/interlinear/{book_slug}/{chapter}-{verse}.htm")
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    words = []
    for t in soup.select("table.tablefloatheb"):
        parts = [x.strip() for x in t.get_text("|", strip=True).split("|")]
        if len(parts) != 6 or not parts[0].isdigit():
            continue
        strongs, _e, translit, hebrew, gloss, parsing = parts
        words.append({
            "strongs": strongs, "translit": translit, "hebrew": hebrew,
            "gloss": gloss.replace("\xa0", " "), "parsing": parsing,
        })
    return words if words else None


def fetch_strongs_definition(number: str) -> dict | None:
    """Strong's 히브리어 번호의 {meta, definition}. meta=원어표기·품사·음역, definition=KJV 뜻풀이(어원 포함)."""
    html = _get(f"https://biblehub.com/hebrew/{number}.htm")
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.select("p")]
    paragraphs = [p for p in paragraphs if p and p != "﻿"]
    meta_idx = next((i for i, p in enumerate(paragraphs) if p.startswith("Original Word:")), None)
    if meta_idx is None:
        return None
    meta = paragraphs[meta_idx]
    definition = paragraphs[meta_idx + 1] if meta_idx + 1 < len(paragraphs) else ""
    return {"meta": meta, "definition": definition}


def research_chapter(book_slug: str, chapter: int, *, max_verse: int = 60,
                      max_strongs_lookups: int = 15, log=None) -> dict:
    """장 전체를 절 1부터 훑어 인터리니어를 모으고, 고유명사(proper) 위주로 Strong's 사전을
    따라가 어원을 가져온다. {"verses": {verse_num: [words...]}, "strongs": {number: {meta, definition}}}"""
    verses: dict[int, list[dict]] = {}
    consecutive_miss = 0
    for v in range(1, max_verse + 1):
        words = fetch_verse_interlinear(book_slug, chapter, v)
        time.sleep(REQUEST_DELAY)
        if words is None:
            consecutive_miss += 1
            if consecutive_miss >= 2 and verses:   # 절이 있다가 2회 연속 없으면 장 끝으로 판단
                break
            continue
        consecutive_miss = 0
        verses[v] = words

    # 고유명사(사람·지명) Strong's 번호를 우선 수집 — 어원 조사 가치가 가장 크다.
    proper_nums, other_nums = [], []
    seen = set()
    for words in verses.values():
        for w in words:
            if w["strongs"] in seen:
                continue
            seen.add(w["strongs"])
            (proper_nums if "proper" in w["parsing"].lower() else other_nums).append(w["strongs"])

    to_lookup = (proper_nums + other_nums)[:max_strongs_lookups]
    strongs_defs = {}
    for num in to_lookup:
        defn = fetch_strongs_definition(num)
        time.sleep(REQUEST_DELAY)
        if defn:
            strongs_defs[num] = defn
    if log:
        log(f"  Bible Hub 조사: {len(verses)}개 절, 단어 {sum(len(w) for w in verses.values())}개, "
            f"Strong's 사전 {len(strongs_defs)}/{len(to_lookup)}개 확인", "INFO")
    return {"verses": verses, "strongs": strongs_defs}


def format_for_prompt(research: dict) -> str:
    """GPT 프롬프트에 그대로 붙여 넣을 텍스트로 정리."""
    lines = ["[Bible Hub 인터리니어 실측 자료 — 아래는 실제로 조회해 온 히브리어 원문·Strong's 정보다. "
             "이 안에 있는 내용은 지어낸 게 아니라 확인된 자료이니 우선 근거로 쓰고, 없는 내용은 이 자료 밖에서 "
             "표준적으로 확실한 것만 보태라.]"]
    for v in sorted(research.get("verses", {})):
        words = research["verses"][v]
        parts = [f"{w['hebrew']}({w['translit']}, {w['strongs']}, {w['gloss']}, {w['parsing']})" for w in words]
        lines.append(f"- {v}절: " + " / ".join(parts))
    if research.get("strongs"):
        lines.append("")
        lines.append("[Strong's 사전 뜻풀이]")
        for num, d in research["strongs"].items():
            lines.append(f"- H{num}: {d['meta']}")
            lines.append(f"  정의: {d['definition']}")
    return "\n".join(lines)
