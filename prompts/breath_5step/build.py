"""
5단 호흡 묵상 GPT 시스템 프롬프트 합본 빌드 스크립트.

사용법:
    python build.py

동작:
    parts/*.md 파일들을 알파벳 순으로 모아 _final_system.md를 생성합니다.
    이 합본 파일이 실제 GPT API 호출 시 system 프롬프트로 사용됩니다.
"""

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PARTS_DIR = SCRIPT_DIR / "parts"
OUTPUT_FILE = SCRIPT_DIR / "_final_system.md"

HEADER = """# 5단 호흡 묵상 생성기 — 시스템 프롬프트

> 이 파일은 자동 생성됩니다. 직접 수정하지 마세요.
> 수정은 `parts/*.md`에서 한 후 `python build.py`를 실행하세요.

---

"""


def build():
    """parts/*.md를 모아 합본을 생성합니다."""
    if not PARTS_DIR.exists():
        raise FileNotFoundError(f"parts 디렉토리가 없습니다: {PARTS_DIR}")

    part_files = sorted(PARTS_DIR.glob("*.md"))
    if not part_files:
        raise FileNotFoundError(f"parts 디렉토리에 .md 파일이 없습니다: {PARTS_DIR}")

    sections = [HEADER]
    for part_file in part_files:
        content = part_file.read_text(encoding="utf-8").strip()
        sections.append(content)
        sections.append("\n\n---\n\n")

    # 마지막 구분선 제거
    if sections[-1] == "\n\n---\n\n":
        sections.pop()

    final_content = "".join(sections)
    OUTPUT_FILE.write_text(final_content, encoding="utf-8")

    line_count = final_content.count("\n") + 1
    print(f"✅ 합본 생성 완료: {OUTPUT_FILE.name}")
    print(f"   - 합쳐진 파트: {len(part_files)}개")
    print(f"   - 총 줄 수: {line_count}줄")
    print(f"   - 파일 크기: {OUTPUT_FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    build()
