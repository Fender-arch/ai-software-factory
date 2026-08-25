"""Pluggable JSON LLM for Coordinator structured tasks."""

from __future__ import annotations

from typing import Any, Protocol


class JsonLLM(Protocol):
    def complete_json(self, system: str, user: str) -> dict[str, Any] | None:
        """Return a JSON object or None when the provider cannot answer."""


class StubLLM:
    def complete_json(self, system: str, user: str) -> dict[str, Any] | None:
        _ = (system, user)
        return None
