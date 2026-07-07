"""Knowledge Agent: the Notion-like library over the 23-chapter AI PM guide."""
from app.agents.base import BaseAgent
from app.services import search as search_svc


class KnowledgeAgent(BaseAgent):
    name = "knowledge"

    def search(self, query: str, limit: int = 20, deep: bool = False):
        """Full-text search with bm25 ranking and highlighted snippets.

        deep=True uses Claude (when available) to expand the query with related
        AI PM terminology before searching, then merges both result sets.
        """
        results = search_svc.search_sections(self.db, query, limit)
        ai_used = False
        if deep and self.ai.available:
            expansion = self.ai.complete(
                "You expand search queries for an AI Product Management knowledge base. "
                "Reply with 5-8 related search terms only, comma-separated, no explanation.",
                f"Query: {query}",
                max_tokens=100,
            )
            if expansion:
                ai_used = True
                seen = {r["section_id"] for r in results}
                extra = [r for r in search_svc.search_sections(self.db, expansion, limit)
                         if r["section_id"] not in seen]
                results = list(results) + extra[: max(0, limit - len(results))]
        if query.strip():
            self.log_event("search", summary=f"Searched knowledge base for: {query}",
                           payload={"results": len(results), "ai_expanded": ai_used})
        return results, ai_used

    def relevant_chapters(self, topic_text: str, limit: int = 3):
        return search_svc.relevant_chapters(self.db, topic_text, limit)

    def chapters(self):
        return self.db.execute("SELECT * FROM kb_chapters ORDER BY number").fetchall()

    def chapter(self, number: int):
        ch = self.db.execute("SELECT * FROM kb_chapters WHERE number=?", (number,)).fetchone()
        if not ch:
            return None, []
        sections = self.db.execute(
            "SELECT * FROM kb_sections WHERE chapter_id=? ORDER BY order_index", (ch["id"],)
        ).fetchall()
        return ch, sections

    def glossary(self, q: str = ""):
        if q:
            return self.db.execute(
                "SELECT * FROM glossary WHERE term LIKE ? OR definition LIKE ? ORDER BY term",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        return self.db.execute("SELECT * FROM glossary ORDER BY term").fetchall()
