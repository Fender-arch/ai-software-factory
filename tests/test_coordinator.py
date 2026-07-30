import pytest

from core.coordinator import AICoordinator, CoordinatorMode, LLMRouter


@pytest.mark.asyncio
async def test_coordinator_stub_mode():
    coord = AICoordinator(LLMRouter(provider="stub"))
    result = await coord.run(CoordinatorMode.DISCOVERY, {"project_id": "x"})
    assert result.mode == CoordinatorMode.DISCOVERY
    assert result.provider == "stub"
    assert "reply_to_customer" in result.output
