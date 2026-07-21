"""공개 주석(HelloAO 퍼블릭 도메인 6종)을 절 단위로 공급한다.

왜(2026-07-21): 예전엔 biblehub.com에서 절당 1요청으로 긁어와 무거워서 '급소 3~8절'에만
붙였고, 그 바람에 KB 절반이 외부 근거 없는 '본문 관찰 (GPT-4o 요약)'이 됐다. 이제 그날
본문의 '모든 절'에 주석을 붙인다.

한 함수로 로컬·클라우드를 모두 처리한다:
  - 로컬(사장님 컴퓨터): data/reference/commentary.db(6종 전권)가 있어 즉시 읽는다.
  - 클라우드(GitHub Actions): 그 파일이 없으므로, 요청한 장의 주석만 HelloAO에서 받아
    같은 DB에 캐시한 뒤 읽는다. HelloAO는 요청 제한·API 키·비용이 없다.
  → 양쪽이 이 모듈 하나를 공유하므로 결과가 항상 같다.

프롬프트가 터지지 않도록 절당 최대 3종·각 420자로 자른다(옛 biblehub 방식과 동일 분량).
"""
import json
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "reference" / "commentary.db"
BASE = "https://bible.helloao.org/api/c"

# HelloAO 주석 id → KB의 source에 쓸 사람이 읽는 이름
SOURCES = {
    "john-gill": "Gill",
    "jamieson-fausset-brown": "JFB",
    "keil-delitzsch": "Keil-Delitzsch",
    "matthew-henry": "Matthew Henry",
    "adam-clarke": "Adam Clarke",
    "tyndale": "Tyndale",
}
# 절당 어느 주석을 우선 쓸지 — 내용이 충실한 순(테스트 실측 기준)
PRIORITY = ["Gill", "Keil-Delitzsch", "JFB", "Matthew Henry", "Adam Clarke", "Tyndale"]

MAX_PER_VERSE = 3     # 한 절에 붙일 주석 종수 상한
MAX_CHARS = 420       # 주석 하나당 글자 상한 (옛 biblehub 방식과 동일)

# 한글 책 이름 → USFM 코드 (HelloAO·commentary.db가 쓰는 코드)
USFM = {
    "창세기": "GEN", "출애굽기": "EXO", "레위기": "LEV", "민수기": "NUM", "신명기": "DEU",
    "여호수아": "JOS", "사사기": "JDG", "룻기": "RUT", "사무엘상": "1SA", "사무엘하": "2SA",
    "열왕기상": "1KI", "열왕기하": "2KI", "역대상": "1CH", "역대하": "2CH", "에스라": "EZR",
    "느헤미야": "NEH", "에스더": "EST", "욥기": "JOB", "시편": "PSA", "잠언": "PRO",
    "전도서": "ECC", "아가": "SNG", "이사야": "ISA", "예레미야": "JER", "예레미야애가": "LAM",
    "에스겔": "EZK", "다니엘": "DAN", "호세아": "HOS", "요엘": "JOL", "아모스": "AMO",
    "오바댜": "OBA", "요나": "JON", "미가": "MIC", "나훔": "NAM", "하박국": "HAB",
    "스바냐": "ZEP", "학개": "HAG", "스가랴": "ZEC", "말라기": "MAL",
    "마태복음": "MAT", "마가복음": "MRK", "누가복음": "LUK", "요한복음": "JHN",
    "사도행전": "ACT", "로마서": "ROM", "고린도전서": "1CO", "고린도후서": "2CO",
    "갈라디아서": "GAL", "에베소서": "EPH", "빌립보서": "PHP", "골로새서": "COL",
    "데살로니가전서": "1TH", "데살로니가후서": "2TH", "디모데전서": "1TI", "디모데후서": "2TI",
    "디도서": "TIT", "빌레몬서": "PHM", "히브리서": "HEB", "야고보서": "JAS",
    "베드로전서": "1PE", "베드로후서": "2PE", "요한일서": "1JN", "요한이서": "2JN",
    "요한삼서": "3JN", "유다서": "JUD", "요한계시록": "REV",
}


def _init(con):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS commentary(
            source TEXT NOT NULL, book TEXT NOT NULL, chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL, text TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_cmt_ref ON commentary(book, chapter, verse);
        CREATE TABLE IF NOT EXISTS done(
            source TEXT NOT NULL, book TEXT NOT NULL, chapter INTEGER NOT NULL,
            n_verses INTEGER, PRIMARY KEY (source, book, chapter));
        """
    )


def _get_json(url, attempts=4):
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(1.5 * (i + 1))
    return None


def _verse_text(item):
    parts = [el for el in item.get("content", []) if isinstance(el, str)]
    parts += [el.get("text", "") for el in item.get("content", []) if isinstance(el, dict)]
    return " ".join(p for p in parts if p).strip()


def _ensure_chapter(con, usfm_book, chapter, log=None):
    """이 장의 6종 주석이 DB에 없으면(=클라우드) HelloAO에서 받아 캐시한다.
    로컬 전권 DB에선 이미 다 있으므로 아무 요청도 안 나간다(no-op)."""
    have = {s for (s,) in con.execute(
        "SELECT source FROM done WHERE book=? AND chapter=?", (usfm_book, chapter))}
    fetched = 0
    for cid, sname in SOURCES.items():
        if sname in have:
            continue
        data = _get_json(f"{BASE}/{cid}/{usfm_book}/{chapter}.json")
        rows = []
        if data:
            for item in data.get("chapter", {}).get("content", []):
                if item.get("type") != "verse":
                    continue
                txt, vno = _verse_text(item), item.get("number")
                if txt and isinstance(vno, int):
                    rows.append((sname, usfm_book, chapter, vno, txt))
        # data가 None(네트워크 실패)이 아니라 '내용 없음'일 때만 done 표시
        if data is not None:
            if rows:
                con.executemany(
                    "INSERT INTO commentary(source,book,chapter,verse,text) VALUES(?,?,?,?,?)", rows)
            con.execute("INSERT OR REPLACE INTO done(source,book,chapter,n_verses) VALUES(?,?,?,?)",
                        (sname, usfm_book, chapter, len(rows)))
            fetched += 1
    if fetched and log:
        log(f"  주석 캐시: {usfm_book} {chapter}장 {fetched}종 HelloAO에서 받음", "INFO")
    con.commit()


def chapter_commentary(book_ko, chapter, verses=None, log=None):
    """{절번호: [(주석명, 본문), ...]} — 그날 본문(verses)의 주석. verses=None이면 그 장 전부.

    로컬 DB 우선, 없으면 HelloAO에서 받아 캐시(양쪽 동일 결과).
    절당 최대 3종·각 420자로 잘라 프롬프트가 터지지 않게 한다."""
    usfm = USFM.get(book_ko)
    if not usfm:
        return {}
    con = sqlite3.connect(DB_PATH)
    try:
        _init(con)
        _ensure_chapter(con, usfm, int(chapter), log=log)
        want = set(verses) if verses else None
        out = {}
        for src, verse, text in con.execute(
            "SELECT source, verse, text FROM commentary WHERE book=? AND chapter=?",
            (usfm, int(chapter))):
            if want is not None and verse not in want:
                continue
            t = text if len(text) <= MAX_CHARS else text[:MAX_CHARS].rsplit(" ", 1)[0] + "…"
            out.setdefault(verse, {})[src] = t
        # 절마다 우선순위 상위 3종만 남긴다
        result = {}
        for v, by_src in out.items():
            picked = [(s, by_src[s]) for s in PRIORITY if s in by_src][:MAX_PER_VERSE]
            if picked:
                result[v] = picked
        return result
    finally:
        con.close()
