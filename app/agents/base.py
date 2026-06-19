import json

from app.services.ai import AIClient


class BaseAgent:
    name = "base"

    def __init__(self, conn, ai: AIClient):
        self.db = conn
        self.ai = ai

    def reference_context(self, query: str = "", project_id=None, max_chars: int = 4000) -> str:
        """Reference-library material in scope for this action (global + the given
        project). Returns a prompt block to prepend to an LLM user message, or ""."""
        from app.services import refs
        try:
            return refs.gather_context(self.db, project_id, query, max_chars)
        except Exception:
            return ""

    @staticmethod
    def _with_context(context: str, user: str) -> str:
        return f"{context}\n\n====\n\n{user}" if context else user

    def log_event(self, action, entity_type=None, entity_id=None, summary="", payload=None):
        self.db.execute(
            "INSERT INTO agent_events(agent, action, entity_type, entity_id, summary, payload) "
            "VALUES (?,?,?,?,?,?)",
            (self.name, action, entity_type, entity_id, summary,
             json.dumps(payload) if payload is not None else None),
        )
