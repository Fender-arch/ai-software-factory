import pytest

from core.coordinator import AICoordinator, CoordinatorMode, LLMRouter


@pytest.mark.asyncio
async def test_coordinator_stub_mode():
    coord = AICoordinator(LLMRouter(provider="stub"))
    result = await coord.run(CoordinatorMode.DISCOVERY, {"project_id": "x"})
    assert result.mode == CoordinatorMode.DISCOVERY
    assert result.provider == "stub"
    assert "reply_to_customer" in result.output

    review = await coord.run(
        CoordinatorMode.REVIEWER,
        {
            "quality_review": {
                "score": 0.4,
                "gaps": ["Vague wording"],
                "contradictions": [],
                "owner_recommendations": ["Tighten metrics"],
                "ready_for_owner": False,
            }
        },
    )
    assert review.output["gaps"] == ["Vague wording"]
    assert review.output["ready_for_owner"] is False
