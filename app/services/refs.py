"""Reference Library: user-provided documents the agents consult.

Two scopes:
  * global  — used by every agent in every action, across all projects.
  * project — used only while working on that one project.

Retrieval is HYBRID:
  * a short reference (<= SHORT_REF_CHARS) is injected in full;
  * a long reference is chunked and FTS-indexed, and only the chunks most
    relevant to the current action's query are injected (RAG).

`gather_context()` returns a ready-to-prepend prompt block, capped at a token
budget so agent calls stay affordable no matter how much material is stored.
"""
from app.services import search as search_svc

SHORT_REF_CHARS = 4000        # at/below this, inject the whole reference
CHUNK_TARGET = 1200           # ~chars per chunk for long references
DEFAULT_CONTEXT_CHARS = 4000  # max chars of reference material per agent action
MAX_LONG_CHUNKS = 8


# ---------------------------------------------------------------- chunking ----
def chunk_text(text: str, target: int = CHUNK_TARGET) -> list[tuple[str, str]]:
    """Split text into (heading, content) chunks on blank-line boundaries,
    accumulating paragraphs up to ~`target` chars. Heading = first line."""
    paras = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    chunks: list[tuple[str, str]] = []
    buf: list[str] = []
    size = 0
    for p in paras:
        if size + len(p) > target and buf:
            block = "\n\n".join(buf)
            chunks.append((block.split("\n", 1)[0][:120], block))
            buf, size = [], 0
        buf.append(p)
        size += len(p)
    if buf:
        block = "\n\n".join(buf)
        chunks.append((block.split("\n", 1)[0][:120], block))
    # very long single paragraphs: hard-split so no chunk is unbounded
    out: list[tuple[str, str]] = []
    for heading, content in chunks:
        if len(content) <= target * 2:
            out.append((heading, content))
        else:
            for i in range(0, len(content), target):
                piece = content[i:i + target]
                out.append((piece.split("\n", 1)[0][:120], piece))
    return out or [("", (text or "").strip())]


def _match_expr(query: str) -> str:
    """Build an FTS MATCH expr from the most informative terms of `query`."""
    kws = search_svc.keywords(query, limit=12)
    if kws:
        return " OR ".join(f'"{k}"' for k in kws)
    return search_svc.fts_query(query)


# ------------------------------------------------------------------- CRUD -----
def add_reference(conn, scope: str, project_id, title: str,
                  filename: str = "", mime: str = "text/plain", text: str = "") -> int:
    """Store a reference and index its chunks. Returns the new reference id."""
    text = (text or "").strip()
    scope = "project" if (scope == "project" and project_id) else "global"
    pid = int(project_id) if scope == "project" else None
    cur = conn.execute(
        "INSERT INTO reference_docs(scope, project_id, title, filename, mime, text, char_count) "
        "VALUES (?,?,?,?,?,?,?)",
        (scope, pid, title.strip() or (filename or "Untitled"), filename, mime, text, len(text)),
    )
    ref_id = cur.lastrowid
    for i, (heading, content) in enumerate(chunk_text(text)):
        conn.execute(
            "INSERT INTO reference_chunks(reference_id, scope, project_id, heading, content, order_index) "
            "VALUES (?,?,?,?,?,?)",
            (ref_id, scope, pid, heading, content, i),
        )
    return ref_id


def list_references(conn, scope: str | None = None):
    sql = ("SELECT r.*, p.name AS project_name FROM reference_docs r "
           "LEFT JOIN projects p ON p.id = r.project_id")
    params: tuple = ()
    if scope:
        sql += " WHERE r.scope = ?"
        params = (scope,)
    sql += " ORDER BY r.created_at DESC"
    return conn.execute(sql, params).fetchall()


def delete_reference(conn, ref_id: int):
    # chunks cascade (FK ON DELETE CASCADE); ref_fts is kept in sync by trigger.
    conn.execute("DELETE FROM reference_docs WHERE id=?", (ref_id,))


def toggle_reference(conn, ref_id: int):
    conn.execute("UPDATE reference_docs SET enabled = 1 - enabled WHERE id=?", (ref_id,))


# -------------------------------------------------------------- retrieval -----
def gather_context(conn, project_id=None, query: str = "",
                   max_chars: int = DEFAULT_CONTEXT_CHARS) -> str:
    """Return a prompt block of reference material in scope for this action.

    Includes every enabled GLOBAL reference plus — when `project_id` is given —
    that project's references. Short refs are injected whole; long refs contribute
    only their query-relevant chunks. Empty string when nothing applies.
    """
    refs = conn.execute(
        "SELECT * FROM reference_docs WHERE enabled=1 AND "
        "(scope='global' OR (scope='project' AND project_id=?)) "
        "ORDER BY scope DESC, created_at DESC",
        (project_id,),
    ).fetchall()
    if not refs:
        return ""

    blocks: list[str] = []
    budget = max_chars
    long_ids: list[int] = []

    # 1) short references in full
    for r in refs:
        if (r["char_count"] or 0) > SHORT_REF_CHARS:
            long_ids.append(r["id"])
            continue
        if budget <= 0:
            break
        body = (r["text"] or "")[:budget]
        tag = "GLOBAL" if r["scope"] == "global" else "PROJECT"
        blocks.append(f"[{tag}] {r['title']}\n{body}")
        budget -= len(body)

    # 2) long references: only the chunks relevant to this action's query
    if long_ids and budget > 200 and query:
        match = _match_expr(query)
        if match:
            placeholders = ",".join("?" * len(long_ids))
            rows = conn.execute(
                f"""
                SELECT d.title AS title, d.scope AS scope, c.heading AS heading, c.content AS content
                FROM ref_fts
                JOIN reference_chunks c ON c.id = ref_fts.rowid
                JOIN reference_docs d ON d.id = c.reference_id
                WHERE ref_fts MATCH ? AND c.reference_id IN ({placeholders})
                ORDER BY bm25(ref_fts) LIMIT ?
                """,
                (match, *long_ids, MAX_LONG_CHUNKS),
            ).fetchall()
            for row in rows:
                if budget <= 200:
                    break
                tag = "GLOBAL" if row["scope"] == "global" else "PROJECT"
                head = f" — {row['heading']}" if row["heading"] else ""
                piece = f"[{tag}] {row['title']}{head}\n{row['content']}"[:budget]
                blocks.append(piece)
                budget -= len(piece)

    if not blocks:
        return ""
    return (
        "Reference material the team has provided. Treat it as authoritative "
        "context for this task and prefer it over general knowledge:\n\n"
        + "\n\n---\n\n".join(blocks)
    )
