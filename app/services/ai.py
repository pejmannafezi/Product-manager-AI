"""Optional Claude API layer. Every caller must work when self.available is False."""
import os

from app import config

try:
    import anthropic
except ImportError:  # the package is optional
    anthropic = None


class AIClient:
    def __init__(self):
        key = os.environ.get("ANTHROPIC_API_KEY", config.ANTHROPIC_API_KEY)
        self.client = anthropic.Anthropic(api_key=key) if (key and anthropic) else None

    @property
    def available(self) -> bool:
        return self.client is not None

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str | None:
        """Returns model text, or None on any failure so callers fall back to rules."""
        if not self.client:
            return None
        try:
            resp = self.client.messages.create(
                model=config.AI_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        except Exception:
            return None


_client: AIClient | None = None


def get_ai() -> AIClient:
    global _client
    if _client is None:
        _client = AIClient()
    return _client
