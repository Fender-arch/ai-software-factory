from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_LLM_MODEL = "llama-3.3-70b-versatile"


class GroqLLM:
    """Groq OpenAI-compatible chat completions, JSON object response."""

    def __init__(self, api_key: str, model: str = DEFAULT_GROQ_LLM_MODEL) -> None:
        self.api_key = api_key
        self.model = model or DEFAULT_GROQ_LLM_MODEL

    def complete_json(self, system: str, user: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None
        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(
                    GROQ_CHAT_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
            if response.status_code >= 400:
                logger.warning(
                    "Groq LLM HTTP %s: %s",
                    response.status_code,
                    response.text[:300],
                )
                return None
            content = (
                (response.json().get("choices") or [{}])[0]
                .get("message", {})
                .get("content")
                or ""
            )
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            logger.exception("Groq LLM JSON complete failed")
            return None
