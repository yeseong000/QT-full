"""OpenBible 관주(cross-references) — generate_kb.py 보조 모듈.

openbible.info가 CC-BY로 공개한, 사람들이 투표로 모은 성경 구절 연결(34만 건)을
읽어, 그날 장의 각 절과 연결되는 구절을 votes(중요도) 순으로 정리해 GPT 프롬프트에
"이 절은 ○○과 연결됨(N표)"으로 끼워 넣는다. 모델은 이걸 배경을 밝힐 '근거'로 쓴다.

두 함정을 처리한다(실측으로 확인됨):
  1) 양방향 인덱싱 — From→To뿐 아니라 To→From 방향도 조회. (삼하 6:3의 급소 대상 15:13은 역방향에만 있음)
  2) 범위 전개 — 'Num.7.4-Num.7.9' 같은 범위(전체 25.6%)를 개별 절로 펼쳐 인덱싱.

데이터는 data/reference/openbible_cross_references.zip(약 2MB)에서 실행 중 읽는다.
파일이 없거나 파싱 실패하면 조용히 빈 결과 → generate_kb는 관주 없이 진행(폴백).
"""
import os
import re
import zipfile
import collections
from pathlib import Path

_DEFAULT_ZIP = Path(__file__).resolve().parent.parent / "data" / "reference" / "openbible_cross_references.zip"

# OSIS 약칭 → 개역개정 한글 책이름 (66권)
OSIS_TO_KO = {
    "Gen": "창세기", "Exod": "출애굽기", "Lev": "레위기", "Num": "민수기", "Deut": "신명기",
    "Josh": "여호수아", "Judg": "사사기", "Ruth": "룻기", "1Sam": "사무엘상", "2Sam": "사무엘하",
    "1Kgs": "열왕기상", "2Kgs": "열왕기하", "1Chr": "역대상", "2Chr": "역대하", "Ezra": "에스라",
    "Neh": "느헤미야", "Esth": "에스더", "Job": "욥기", "Ps": "시편", "Prov": "잠언",
    "Eccl": "전도서", "Song": "아가", "Isa": "이사야", "Jer": "예레미야", "Lam": "예레미야애가",
    "Ezek": "에스겔", "Dan": "다니엘", "Hos": "호세아", "Joel": "요엘", "Amos": "아모스",
    "Obad": "오바댜", "Jonah": "요나", "Mic": "미가", "Nah": "나훔", "Hab": "하박국",
    "Zeph": "스바냐", "Hag": "학개", "Zech": "스가랴", "Mal": "말라기", "Matt": "마태복음",
    "Mark": "마가복음", "Luke": "누가복음", "John": "요한복음", "Acts": "사도행전", "Rom": "로마서",
    "1Cor": "고린도전서", "2Cor": "고린도후서", "Gal": "갈라디아서", "Eph": "에베소서", "Phil": "빌립보서",
    "Col": "골로새서", "1Thess": "데살로니가전서", "2Thess": "데살로니가후서", "1Tim": "디모데전서",
    "2Tim": "디모데후서", "Titus": "디도서", "Phlm": "빌레몬서", "Heb": "히브리서", "Jas": "야고보서",
    "1Pet": "베드로전서", "2Pet": "베드로후서", "1John": "요한일서", "2John": "요한이서",
    "3John": "요한삼서", "Jude": "유다서", "Rev": "요한계시록",
}
KO_TO_OSIS = {ko: osis for osis, ko in OSIS_TO_KO.items()}

_index_cache = None  # (fwd, rev) 캐시 — 프로세스당 한 번만 빌드


def _parse_ref(ref):
    m = re.match(r"^([\w]+)\.(\d+)\.(\d+)$", ref)
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def _expand(ref):
    """단일 절 또는 범위를 개별 절 문자열 리스트로. 같은 책·장 범위만 절 단위로 펼침."""
    if "-" not in ref:
        return [ref] if _parse_ref(ref) else []
    a, b = ref.split("-", 1)
    pa, pb = _parse_ref(a), _parse_ref(b)
    if not pa or not pb:
        return [a]
    if pa[0] == pb[0] and pa[1] == pb[1] and pb[2] >= pa[2]:
        return [f"{pa[0]}.{pa[1]}.{v}" for v in range(pa[2], pb[2] + 1)]
    return [a, b]


def _build_index(zip_path=None, min_votes=1):
    """zip 안의 cross_references.txt를 읽어 양방향 인덱스를 만든다. 실패 시 (빈, 빈)."""
    zip_path = Path(zip_path) if zip_path else _DEFAULT_ZIP
    fwd = collections.defaultdict(list)
    rev = collections.defaultdict(list)
    if not zip_path.exists():
        return fwd, rev
    try:
        with zipfile.ZipFile(zip_path) as z:
            name = next((n for n in z.namelist() if n.endswith(".txt")), None)
            if not name:
                return fwd, rev
            with z.open(name) as f:
                first = True
                for raw in f:
                    line = raw.decode("utf-8", "replace")
                    if first:  # 헤더
                        first = False
                        continue
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 3:
                        continue
                    frm, to, votes = parts[0], parts[1], parts[2]
                    try:
                        votes = int(votes)
                    except ValueError:
                        continue
                    if votes < min_votes:
                        continue
                    for v in _expand(frm):
                        fwd[v].append((to, votes))
                    for v in _expand(to):
                        rev[v].append((frm, votes))
    except Exception:
        return collections.defaultdict(list), collections.defaultdict(list)
    return fwd, rev


def _get_index(zip_path=None):
    global _index_cache
    if _index_cache is None:
        _index_cache = _build_index(zip_path)
    return _index_cache


def osis_to_korean(ref):
    """'1Chr.15.13' -> '역대상 15:13' · 'Num.7.4-Num.7.9' -> '민수기 7:4-9'. 모르면 원본."""
    def one(r):
        p = _parse_ref(r)
        if not p:
            return r
        book, ch, v = p
        return f"{OSIS_TO_KO.get(book, book)} {ch}:{v}"
    if "-" in ref:
        a, b = ref.split("-", 1)
        pa, pb = _parse_ref(a), _parse_ref(b)
        if pa and pb and pa[0] == pb[0] and pa[1] == pb[1]:
            return f"{OSIS_TO_KO.get(pa[0], pa[0])} {pa[1]}:{pa[2]}-{pb[2]}"
        return f"{one(a)}-{one(b)}"
    return one(ref)


def lookup_verse(book_ko, chapter, verse, *, top_n=6, min_votes=2, zip_path=None):
    """한 절의 관주를 votes 내림차순으로 [(한글참조, votes)]. book_ko는 개역개정 책이름."""
    osis = KO_TO_OSIS.get(book_ko)
    if not osis:
        return []
    fwd, rev = _get_index(zip_path)
    key = f"{osis}.{chapter}.{verse}"
    best = {}
    for to, votes in fwd.get(key, []):
        if votes > best.get(to, 0):
            best[to] = votes
    for frm, votes in rev.get(key, []):
        if votes > best.get(frm, 0):
            best[frm] = votes
    items = [(osis_to_korean(r), v) for r, v in best.items() if v >= min_votes]
    items.sort(key=lambda x: -x[1])
    return items[:top_n]


def build_chapter_xref_text(book_ko, chapter, verse_numbers, *, top_n=6, min_votes=2, zip_path=None):
    """그날 장의 각 절 관주를 프롬프트용 텍스트로. 연결이 하나도 없으면 None."""
    lines = []
    for v in verse_numbers:
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        refs = lookup_verse(book_ko, chapter, v, top_n=top_n, min_votes=min_votes, zip_path=zip_path)
        if not refs:
            continue
        joined = ", ".join(f"{r}({n}표)" for r, n in refs)
        lines.append(f"- {chapter}:{v} ↔ {joined}")
    if not lines:
        return None
    header = (
        "[OpenBible 관주(cross-reference) — openbible.info가 CC-BY로 공개한, 사람들이 투표로 모은 "
        "성경 구절 연결이다. 표(votes)가 많을수록 중요하게 여겨진 연결이며, 이건 '어디를 보라'는 "
        "실제 근거다. 아래 연결 구절을 참고해, 특히 [배경] 항목(낯선 물건·제도·행동, 설명 없는 인과)의 "
        "배경·이유를 밝힐 때 근거로 활용하라. 단 연결된 구절의 내용을 지어내지 말고, 표준적으로 확실한 "
        "것만 보태며, 불확실하면 confidence를 낮춰라.]"
    )
    return header + "\n" + "\n".join(lines)


def top_crux_verses(book_ko, chapter, verse_numbers, *, k=5, zip_path=None):
    """배경 급소 절 k개 — '연결 개수(breadth)'가 넓은 절 우선(동률이면 총 득표).

    옛 방식은 '단일 최고 득표' 한 개로 줄 세웠는데, 그러면 역대상 같은 평행(쌍둥이)
    본문이 있는 절이 몰표로 독식하고, 정작 여러 책이 두루 가리키는 언약·메시아 급소
    절(예: 삼하 7:12·16)이 밀려났다. 무료 검증(2026-07-15, 삼하 5·6·7·11)에서
    연결 개수 기준의 급소 포착률이 가장 높았다(71% vs 단일최고 29%).
    """
    scored = []
    for v in verse_numbers:
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        refs = lookup_verse(book_ko, chapter, v, top_n=1000, min_votes=1, zip_path=zip_path)
        if refs:
            count = len(refs)
            total = sum(n for _, n in refs)
            scored.append((v, count, total))
    scored.sort(key=lambda x: (-x[1], -x[2]))
    return [v for v, _, _ in scored[:k]]


if __name__ == "__main__":
    import sys
    book = sys.argv[1] if len(sys.argv) > 1 else "사무엘하"
    ch = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    fwd, rev = _get_index()
    print(f"인덱스: 정방향 키 {len(fwd):,} · 역방향 키 {len(rev):,}")
    txt = build_chapter_xref_text(book, ch, range(1, 30))
    print(txt or "(관주 없음)")
