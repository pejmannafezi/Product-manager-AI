"""FTS5 search over the knowledge base."""
import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has", "have",
    "how", "in", "is", "it", "its", "of", "on", "or", "our", "should", "that", "the",
    "their", "this", "to", "we", "what", "when", "which", "who", "will", "with", "you",
    "your", "i", "my", "me", "do", "does", "can", "not", "all", "they",
}


def fts_query(raw: str) -> str:
    """Build a safe FTS5 MATCH expression: quoted terms OR-joined."""
    terms = re.findall(r"[A-Za-z0-9]+", raw or "")
    terms = [t for t in terms if len(t) > 1][:12]
    if not terms:
        return ""
    return " OR ".join(f'"{t}"' for t in terms)


def keywords(text: str, limit: int = 8) -> list[str]:
    """Top keywords by frequency, stopwords removed. Used for relevant-chapter lookup."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", (text or "").lower())
    freq: dict[str, int] = {}
    for w in words:
        if w in STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:limit]]


def search_sections(conn, raw_query: str, limit: int = 20):
    match = fts_query(raw_query)
    if not match:
        return []
    return conn.execute(
        """
        SELECT s.id AS section_id, s.heading, c.number AS chapter_number, c.title AS chapter_title,
               snippet(kb_fts, 1, '<mark>', '</mark>', '…', 24) AS snip,
               bm25(kb_fts) AS rank
        FROM kb_fts
        JOIN kb_sections s ON s.id = kb_fts.rowid
        JOIN kb_chapters c ON c.id = s.chapter_id
        WHERE kb_fts MATCH ?
        ORDER BY rank LIMIT ?
        """,
        (match, limit),
    ).fetchall()


def relevant_chapters(conn, text: str, limit: int = 3):
    """Aggregate bm25 by chapter for the top keywords of `text`."""
    kws = keywords(text)
    if not kws:
        return []
    match = " OR ".join(f'"{k}"' for k in kws)
    # bm25() is only valid in the immediate FTS query context (SQLite flattens
    # subqueries, so GROUP BY around it fails); aggregate per chapter in Python
    rows = conn.execute(
        """
        SELECT c.id, c.number, c.title, -bm25(kb_fts) AS relevance
        FROM kb_fts
        JOIN kb_sections s ON s.id = kb_fts.rowid
        JOIN kb_chapters c ON c.id = s.chapter_id
        WHERE kb_fts MATCH ?
        ORDER BY bm25(kb_fts) LIMIT 200
        """,
        (match,),
    ).fetchall()
    agg: dict[int, dict] = {}
    for r in rows:
        entry = agg.setdefault(r["id"], {"id": r["id"], "number": r["number"],
                                         "title": r["title"], "relevance": 0.0})
        entry["relevance"] += r["relevance"]
    return sorted(agg.values(), key=lambda e: -e["relevance"])[:limit]
