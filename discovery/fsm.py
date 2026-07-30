from __future__ import annotations

from core.models import ProjectStatus

# Logical Discovery stages (finer than ProjectStatus; used by future interview logic)
DISCOVERY_STAGES = [
    "PROJECT_CREATED",
    "UNDERSTANDING_IDEA",
    "BUSINESS_CONTEXT",
    "USERS",
    "FUNCTIONAL",
    "NON_FUNCTIONAL",
    "INTEGRATIONS",
    "RISKS",
    "REVIEW",
    "READY_FOR_OWNER",
]


def status_after_customer_message(current: ProjectStatus) -> ProjectStatus:
    if current == ProjectStatus.NEW:
        return ProjectStatus.INTERVIEW
    if current == ProjectStatus.WAITING_CUSTOMER:
        return ProjectStatus.INTERVIEW
    return current
