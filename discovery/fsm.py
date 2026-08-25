from __future__ import annotations

from enum import Enum

from core.models import ProjectStatus


class DiscoveryStage(str, Enum):
    PROJECT_CREATED = "PROJECT_CREATED"
    UNDERSTANDING_IDEA = "UNDERSTANDING_IDEA"
    BUSINESS_CONTEXT = "BUSINESS_CONTEXT"
    USERS = "USERS"
    FUNCTIONAL = "FUNCTIONAL"
    DATA = "DATA"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    INTEGRATIONS = "INTEGRATIONS"
    ACCEPTANCE = "ACCEPTANCE"
    RISKS = "RISKS"
    REVIEW = "REVIEW"
    READY_FOR_OWNER = "READY_FOR_OWNER"


DISCOVERY_STAGES: list[DiscoveryStage] = list(DiscoveryStage)

_STAGE_INDEX = {stage: idx for idx, stage in enumerate(DISCOVERY_STAGES)}


def parse_stage(value: str | DiscoveryStage | None) -> DiscoveryStage:
    if value is None:
        return DiscoveryStage.PROJECT_CREATED
    if isinstance(value, DiscoveryStage):
        return value
    try:
        return DiscoveryStage(value)
    except ValueError:
        return DiscoveryStage.PROJECT_CREATED


def next_stage(current: DiscoveryStage) -> DiscoveryStage:
    idx = _STAGE_INDEX[current]
    if idx >= len(DISCOVERY_STAGES) - 1:
        return current
    return DISCOVERY_STAGES[idx + 1]


def previous_stage(current: DiscoveryStage) -> DiscoveryStage:
    idx = _STAGE_INDEX[current]
    if idx <= 0:
        return current
    return DISCOVERY_STAGES[idx - 1]


def advance_stage(current: DiscoveryStage, *, steps: int = 1) -> DiscoveryStage:
    stage = current
    for _ in range(max(0, steps)):
        nxt = next_stage(stage)
        if nxt == stage:
            break
        stage = nxt
    return stage


def regress_stage(current: DiscoveryStage, *, steps: int = 1) -> DiscoveryStage:
    stage = current
    for _ in range(max(0, steps)):
        prev = previous_stage(stage)
        if prev == stage:
            break
        stage = prev
    return stage


def project_status_for_stage(stage: DiscoveryStage) -> ProjectStatus:
    if stage == DiscoveryStage.PROJECT_CREATED:
        return ProjectStatus.NEW
    if stage == DiscoveryStage.REVIEW:
        return ProjectStatus.ANALYZING
    if stage == DiscoveryStage.READY_FOR_OWNER:
        return ProjectStatus.WAITING_OWNER
    return ProjectStatus.INTERVIEW


def status_after_customer_message(current: ProjectStatus) -> ProjectStatus:
    """Legacy helper: first customer message leaves NEW."""
    if current == ProjectStatus.NEW:
        return ProjectStatus.INTERVIEW
    if current == ProjectStatus.WAITING_CUSTOMER:
        return ProjectStatus.INTERVIEW
    return current


def stage_after_project_created(current: DiscoveryStage) -> DiscoveryStage:
    if current == DiscoveryStage.PROJECT_CREATED:
        return DiscoveryStage.UNDERSTANDING_IDEA
    return current
