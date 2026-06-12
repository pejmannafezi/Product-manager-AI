import json

from app.services.ai import AIClient


class BaseAgent:
    name = "base"

    def __init__(self, conn, ai: AIClient):
        self.db = conn
        self.ai = ai

    def log_event(self, action, entity_type=None, entity_id=None, summary="", payload=None):
        self.db.execute(
            "INSERT INTO agent_events(agent, action, entity_type, entity_id, summary, payload) "
            "VALUES (?,?,?,?,?,?)",
            (self.name, action, entity_type, entity_id, summary,
             json.dumps(payload) if payload is not None else None),
        )
