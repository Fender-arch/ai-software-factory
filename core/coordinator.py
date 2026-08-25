from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CoordinatorMode(str, Enum):
    DISCOVERY = "discovery"
    REVIEWER = "reviewer"
    ARCHITECT = "architect"
    PLANNER = "planner"
    DEVELOPER = "developer"
    QA = "qa"


@dataclass
class CoordinatorResult:
    mode: CoordinatorMode
    output: dict[str, Any]
    provider: str


class LLMRouter:
    """Placeholder LLM router. Real providers plug in later."""

    def __init__(self, provider: str = "stub") -> None:
        self.provider = provider

    async def complete(self, mode: CoordinatorMode, context: dict[str, Any]) -> dict[str, Any]:
        if self.provider == "stub":
            if mode == CoordinatorMode.DISCOVERY:
                note = "Deterministic Discovery owns KG writes; LLM stub only annotates."
                if context.get("task") == "adapt_outline":
                    return {
                        "skip_topic_ids": [],
                        "keep_topic_ids": [],
                        "extra_topics": [],
                        "capabilities": [],
                        "question_overrides": {},
                        "mode": mode.value,
                        "note": note,
                    }
                return {
                    "reply_to_customer": context.get("deterministic_reply")
                    or "Thanks — I recorded your message.",
                    "extracted": [],
                    "open_questions": [],
                    "next_status": context.get("status", "INTERVIEW"),
                    "mode": mode.value,
                    "echo_context_keys": sorted(context.keys()),
                    "note": note,
                }
            if mode == CoordinatorMode.PLANNER:
                return {
                    "tasks": context.get("planned_tasks", []),
                    "next_status": context.get("status", "READY"),
                    "mode": mode.value,
                    "echo_context_keys": sorted(context.keys()),
                    "note": "Deterministic Planner owns task writes; LLM stub only annotates.",
                }
            if mode == CoordinatorMode.REVIEWER:
                review = context.get("quality_review") or {}
                return {
                    "score": review.get("score", 0.5),
                    "gaps": review.get("gaps", []),
                    "contradictions": review.get("contradictions", []),
                    "owner_recommendations": review.get("owner_recommendations", []),
                    "ready_for_owner": review.get("ready_for_owner", False),
                    "mode": mode.value,
                    "echo_context_keys": sorted(context.keys()),
                    "note": "Deterministic quality scan owns gaps; LLM stub only annotates.",
                }
            return {
                "reply_to_customer": (
                    "Thanks — I recorded your message. Mode LLM is not wired yet."
                ),
                "mode": mode.value,
                "echo_context_keys": sorted(context.keys()),
            }
        if self.provider == "groq":
            from integrations.llm import complete_json

            if mode == CoordinatorMode.DISCOVERY and context.get("task") == "adapt_outline":
                system = str(context.get("system_prompt") or "")
                user = str(context.get("user_prompt") or "")
                proposed = complete_json(system, user) or {}
                return {**proposed, "mode": mode.value, "provider": "groq"}
            # Customer-facing turns stay deterministic; Groq is used inside Discovery adapt.
            if mode == CoordinatorMode.DISCOVERY:
                return {
                    "reply_to_customer": context.get("deterministic_reply")
                    or "Thanks — I recorded your message.",
                    "extracted": [],
                    "open_questions": [],
                    "next_status": context.get("status", "INTERVIEW"),
                    "mode": mode.value,
                    "echo_context_keys": sorted(context.keys()),
                    "note": "Deterministic Discovery owns KG writes; Groq adapts the TZ outline.",
                }
            if mode == CoordinatorMode.PLANNER:
                return {
                    "tasks": context.get("planned_tasks", []),
                    "next_status": context.get("status", "READY"),
                    "mode": mode.value,
                    "echo_context_keys": sorted(context.keys()),
                    "note": "Deterministic Planner owns task writes; LLM annotates.",
                }
            if mode == CoordinatorMode.REVIEWER:
                review = context.get("quality_review") or {}
                return {
                    "score": review.get("score", 0.5),
                    "gaps": review.get("gaps", []),
                    "contradictions": review.get("contradictions", []),
                    "owner_recommendations": review.get("owner_recommendations", []),
                    "ready_for_owner": review.get("ready_for_owner", False),
                    "mode": mode.value,
                    "echo_context_keys": sorted(context.keys()),
                    "note": "Deterministic quality scan owns gaps; LLM annotates.",
                }
            return {
                "reply_to_customer": context.get("deterministic_reply")
                or "Thanks — I recorded your message.",
                "mode": mode.value,
                "echo_context_keys": sorted(context.keys()),
            }
        raise NotImplementedError(f"LLM provider '{self.provider}' is not implemented")


class AICoordinator:
    def __init__(self, router: LLMRouter | None = None) -> None:
        self.router = router or LLMRouter()

    async def run(
        self, mode: CoordinatorMode, context: dict[str, Any]
    ) -> CoordinatorResult:
        output = await self.router.complete(mode, context)
        return CoordinatorResult(mode=mode, output=output, provider=self.router.provider)
