from __future__ import annotations

from typing import Any

from integrations.llm.base import JsonLLM, StubLLM


def get_llm_provider() -> JsonLLM:
    from core.config import get_settings

    settings = get_settings()
    provider = (settings.llm_provider or "stub").strip().lower()
    if provider == "stub":
        return StubLLM()
    if provider == "groq":
        from integrations.llm.groq import DEFAULT_GROQ_LLM_MODEL, GroqLLM

        model = settings.llm_model or DEFAULT_GROQ_LLM_MODEL
        if model.startswith("whisper"):
            model = DEFAULT_GROQ_LLM_MODEL
        return GroqLLM(api_key=settings.groq_api_key, model=model)
    return StubLLM()


def complete_json(system: str, user: str) -> dict[str, Any] | None:
    return get_llm_provider().complete_json(system, user)
