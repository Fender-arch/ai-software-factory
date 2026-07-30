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
            return {
                "reply_to_customer": (
                    "Thanks — I recorded your message. Discovery LLM is not wired yet."
                ),
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
