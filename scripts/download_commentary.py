"""공개 주석(퍼블릭 도메인) 6종을 HelloAO API에서 통째로 받아 로컬 SQLite에 저장한다.

왜(2026-07-21): 지금까지는 biblehub.com에서 절당 1요청으로 주석을 긁어와, 무거워서
'급소 3~8절'에만 붙였다(generate_kb.py:421). 그 바람에 KB의 절반 이상이 외부 근거 없는
'본문 관찰 (GPT-4o 요약)'로 채워졌다. HelloAO는 퍼블릭 도메인 주석을 절 단위 JSON으로
요청 제한·API 키 없이 공식 제공하므로, 한 번 받아 로컬에 두면 모든 절에 주석을 붙일 수 있다.

받는 것 — Gill · JFB · Keil-Delitzsch · Matthew Henry · Adam Clarke · Tyndale (전부 PD).
저장 — data/reference/commentary.db, 테이블 commentary(source, book, chapter, verse, text).
       (book은 USFM 코드: GEN·2SA 등. openbible 관주 zip과 같은 '로컬 자료' 취급.)

중간에 끊겨도 다시 실행하면 이미 받은 (source, book, chapter)는 건너뛴다(이어받기).

사용:
  python scripts/download_commentary.py            # 6종 전부 받기
  python scripts/download_commentary.py --test      # 삼하(2SA)만 받아 동작 확인
  python scripts/download_commentary.py --stats      # 받은 현황만 출력
"""
import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "reference" / "commentary.db"
BASE = "https://bible.helloao.org/api/c"

# id → 사람이 읽는 이름 (KB source 필드에 이 이름을 쓴다)
SOURCES = {
    "john-gill": "Gill",
    "jamieson-fausset-brown": "JFB",
    "keil-delitzsch": "Keil-Delitzsch",
    "matthew-henry": "Matthew Henry",
    "adam-clarke": "Adam Clarke",
    "tyndale": "Tyndale",
}


def _get_json(url, attempts=4):
    """네트워크가 흔들려도 몇 번 다시 시도. 끝내 실패하면 None."""
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(1.5 * (i + 1))
    print(f"    [실패] {url} — {last}")
    return None


def _verse_text(item):
    """한 절 항목에서 주석 본문만 뽑는다. content는 문자열 리스트지만,
    혹시 문자열이 아닌 요소(각주 참조 등)가 섞이면 건너뛴다."""
    parts = []
    for el in item.get("content", []):
        if isinstance(el, str):
            parts.append(el)
        elif isinstance(el, dict):
            t = el.get("text")
            if isinstance(t, str):
                parts.append(t)
    return " ".join(parts).strip()


def _init_db(con):
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS commentary(
            source  TEXT NOT NULL,   -- 'Gill' 등 사람이 읽는 이름
            book    TEXT NOT NULL,   -- USFM 코드: GEN, 2SA ...
            chapter INTEGER NOT NULL,
            verse   INTEGER NOT NULL,
            text    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cmt_ref ON commentary(book, chapter, verse);
        -- 이어받기용: 어느 (source, book, chapter)까지 다 받았는지 기록
        CREATE TABLE IF NOT EXISTS done(
            source TEXT NOT NULL, book TEXT NOT NULL, chapter INTEGER NOT NULL,
            n_verses INTEGER,
            PRIMARY KEY (source, book, chapter)
        );
        """
    )
    con.commit()


def download(con, only_book=None):
    _init_db(con)
    done = {(s, b, c) for s, b, c in con.execute("SELECT source, book, chapter FROM done")}
    total_ins = 0

    for cid, sname in SOURCES.items():
        books = _get_json(f"{BASE}/{cid}/books.json")
        if not books:
            print(f"[{sname}] books.json 실패 — 이 주석 건너뜀")
            continue
        books = books.get("books") or books
        if only_book:
            books = [b for b in books if b.get("id") == only_book]
        n_ch = sum(b.get("numberOfChapters", 0) for b in books)
        print(f"[{sname}] {len(books)}권 · {n_ch}장 — 시작")

        seen = 0
        for b in books:
            book_id = b.get("id")
            for ch in range(1, b.get("numberOfChapters", 0) + 1):
                seen += 1
                if (sname, book_id, ch) in done:
                    continue
                data = _get_json(f"{BASE}/{cid}/{book_id}/{ch}.json")
                if not data:
                    continue  # 이 장은 다음 실행 때 다시 시도(done에 안 넣음)
                rows = []
                for item in data.get("chapter", {}).get("content", []):
                    if item.get("type") != "verse":
                        continue
                    txt = _verse_text(item)
                    vno = item.get("number")
                    if txt and isinstance(vno, int):
                        rows.append((sname, book_id, ch, vno, txt))
                if rows:
                    con.executemany(
                        "INSERT INTO commentary(source,book,chapter,verse,text) VALUES(?,?,?,?,?)",
                        rows,
                    )
                    total_ins += len(rows)
                con.execute(
                    "INSERT OR REPLACE INTO done(source,book,chapter,n_verses) VALUES(?,?,?,?)",
                    (sname, book_id, ch, len(rows)),
                )
                if seen % 50 == 0:
                    con.commit()
                    print(f"  [{sname}] {seen}/{n_ch}장 · 누적 {total_ins}절")
        con.commit()
        print(f"[{sname}] 완료")

    return total_ins


def stats(con):
    if not DB_PATH.exists():
        print("아직 받은 게 없습니다.")
        return
    print(f"DB: {DB_PATH}  ({DB_PATH.stat().st_size/1024/1024:.1f} MB)")
    print(f"{'주석':<18}{'절 수':>9}{'장 수':>8}")
    print("-" * 36)
    for s, nv, nc in con.execute(
        "SELECT source, COUNT(*), COUNT(DISTINCT book||':'||chapter) "
        "FROM commentary GROUP BY source ORDER BY COUNT(*) DESC"
    ):
        print(f"{s:<18}{nv:>9,}{nc:>8,}")
    tot = con.execute("SELECT COUNT(*) FROM commentary").fetchone()[0]
    print("-" * 36)
    print(f"{'합계':<18}{tot:>9,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="삼하(2SA)만 받아 동작 확인")
    ap.add_argument("--stats", action="store_true", help="받은 현황만 출력")
    args = ap.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        if args.stats:
            stats(con)
        else:
            t0 = time.time()
            n = download(con, only_book="2SA" if args.test else None)
            print(f"\n총 {n:,}절 저장 · {time.time()-t0:.0f}초")
            stats(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
