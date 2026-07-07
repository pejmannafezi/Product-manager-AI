"""Ingest the 23-chapter AI PM guide (.docx) into the knowledge base.

Usage:
    python scripts/ingest_docx.py data/guide.docx [--replace]

Splits on paragraphs matching '^Chapter N: Title' (regex on text, not styles),
sections on Heading-styled paragraphs or ~3000-char chunks, flattens tables,
and harvests glossary terms from any chapter whose title mentions 'glossary'.
The kb_fts index is maintained by triggers.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import docx  # noqa: E402

from app import db as dbmod  # noqa: E402

CHAPTER_RE = re.compile(r"^Chapter\s+(\d+)\s*:\s*(.+)$")
SECTION_NUM_RE = re.compile(r"^(\d{1,2})\.\d+\s+\S")
SECTION_CHARS = 3000


def iter_blocks(document):
    """Yield (style_name, text) for paragraphs and flattened tables in order."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            p = Paragraph(child, document)
            if p.text.strip():
                yield p.style.name if p.style else "Normal", p.text.strip()
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            for row in table.rows:
                line = " | ".join(c.text.strip() for c in row.cells)
                if line.strip(" |"):
                    yield "Table", line


def _looks_like_title(text: str) -> bool:
    return 0 < len(text) < 80 and "☐" not in text and not text.endswith(".")


def split_chapters(blocks):
    """Split on 'Chapter N: Title' lines. Two fallbacks for chapters whose title
    line lacks the prefix: (a) a numbered section 'N.1 …' for the next chapter
    number promotes the preceding short line to that chapter's title; (b) a short
    standalone 'Glossary' line after chapter 22 starts the final chapter."""
    chapters = []  # (number, title, [(style, text), ...])
    current = (0, "Introduction", [])

    def push():
        if current[2] or current[0]:
            chapters.append(current)

    for style, text in blocks:
        m = CHAPTER_RE.match(text)
        if m:
            push()
            current = (int(m.group(1)), m.group(2).strip(), [])
            continue
        sm = SECTION_NUM_RE.match(text)
        if sm and int(sm.group(1)) == current[0] + 1:
            number = int(sm.group(1))
            title, carried = f"Chapter {number}", []
            # the chapter title is usually a short standalone line shortly
            # before the 'N.1' section, with intro paragraphs in between
            body = current[2]
            for j in range(len(body) - 1, max(len(body) - 6, -1), -1):
                if _looks_like_title(body[j][1]):
                    title = body[j][1]
                    carried = body[j + 1:]
                    del body[j:]
                    break
            push()
            current = (number, title, carried + [(style, text)])
            continue
        if current[0] == 22 and _looks_like_title(text) and "glossary" in text.lower():
            push()
            current = (23, text, [])
            continue
        current[2].append((style, text))
    push()
    return chapters


def split_sections(blocks):
    """Sections start at Heading-styled paragraphs; headingless chapters get
    ~SECTION_CHARS chunks on paragraph boundaries so FTS snippets stay useful."""
    sections = []  # (heading, level, content)
    has_headings = any(s.startswith("Heading") for s, _ in blocks)
    if has_headings:
        heading, level, buf = None, 2, []
        for style, text in blocks:
            if style.startswith("Heading"):
                if buf or heading:
                    sections.append((heading, level, "\n".join(buf)))
                heading = text
                level = int(style.split()[-1]) if style.split()[-1].isdigit() else 2
                buf = []
            else:
                buf.append(text)
        if buf or heading:
            sections.append((heading, level, "\n".join(buf)))
    else:
        buf, size = [], 0
        for _, text in blocks:
            buf.append(text)
            size += len(text)
            if size >= SECTION_CHARS:
                sections.append((None, 2, "\n".join(buf)))
                buf, size = [], 0
        if buf:
            sections.append((None, 2, "\n".join(buf)))
    return sections


def harvest_glossary(conn, chapter_id, title, blocks):
    """The glossary chapter lists each term as a short standalone paragraph
    followed by its definition paragraph. Pair them up."""
    if "glossary" not in title.lower() and "vocabulary" not in title.lower():
        return 0
    conn.execute("DELETE FROM glossary WHERE chapter_id IS NOT NULL")
    texts = [t for _, t in blocks]
    count = 0
    for i in range(len(texts) - 1):
        term, definition = texts[i].strip(), texts[i + 1].strip()
        if (2 < len(term) <= 60
                and "☐" not in term and ":" not in term
                and not term.endswith((".", "?"))
                and term[0].isupper()
                and len(term.split()) <= 7
                and len(definition) >= 40
                and len(definition.split()) > 7):
            conn.execute(
                "INSERT INTO glossary(term, definition, chapter_id) VALUES (?,?,?) "
                "ON CONFLICT(term) DO UPDATE SET definition=excluded.definition, "
                "chapter_id=excluded.chapter_id",
                (term, definition, chapter_id),
            )
            count += 1
    return count


def ingest(path: Path, replace: bool = False) -> int:
    document = docx.Document(str(path))
    blocks = list(iter_blocks(document))
    chapters = split_chapters(blocks)

    dbmod.init_db()
    with dbmod.db_session() as conn:
        if replace:
            conn.execute("DELETE FROM kb_sections")
            conn.execute("DELETE FROM kb_chapters")
        glossary_total = 0
        for number, title, body in chapters:
            text_all = "\n".join(t for _, t in body)
            cur = conn.execute(
                "INSERT INTO kb_chapters(number, title, summary, word_count) VALUES (?,?,?,?) "
                "ON CONFLICT(number) DO UPDATE SET title=excluded.title, "
                "summary=excluded.summary, word_count=excluded.word_count",
                (number, title, text_all[:400], len(text_all.split())),
            )
            chapter_id = cur.lastrowid or conn.execute(
                "SELECT id FROM kb_chapters WHERE number=?", (number,)).fetchone()["id"]
            conn.execute("DELETE FROM kb_sections WHERE chapter_id=?", (chapter_id,))
            for idx, (heading, level, content) in enumerate(split_sections(body)):
                conn.execute(
                    "INSERT INTO kb_sections(chapter_id, heading, level, order_index, content) "
                    "VALUES (?,?,?,?,?)",
                    (chapter_id, heading, level, idx, content),
                )
            glossary_total += harvest_glossary(conn, chapter_id, title, body)

    real_chapters = [c for c in chapters if c[0] > 0]
    print(f"Ingested {len(real_chapters)} chapters "
          f"(+{len(chapters) - len(real_chapters)} intro), {glossary_total} glossary terms.")
    if len(real_chapters) != 23:
        print(f"WARNING: expected 23 chapters, found {len(real_chapters)}.")
    return len(real_chapters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("docx_path", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    ingest(args.docx_path, args.replace)
