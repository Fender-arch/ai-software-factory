"""Human-in-the-loop gate after draft TZ (owner approve / changes / reject)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from core.client_estimate import (
    attach_client_estimate_to_draft,
    client_estimate_from_artifact,
    client_estimate_report_from_artifact,
    customer_estimate_view,
)
from core.config import get_settings
from core.estimate import estimate_from_artifact
from core.models import Entity, Project, ProjectStatus
from discovery.fsm import DiscoveryStage
from discovery.quality import evaluate_spec_quality
from knowledge.repository import KnowledgeRepository


class HitlAction(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


@dataclass
class HitlResult:
    project_id: uuid.UUID
    action: HitlAction
    project_status: ProjectStatus
    artifact_id: uuid.UUID | None
    decision_id: uuid.UUID | None
    message: str
    human_decision_required: bool = False


class HitlError(ValueError):
    """Domain error for HITL transitions."""


def assert_owner_actor(actor_telegram_id: str | None) -> None:
    """If OWNER_TELEGRAM_ID is set, actor must match. Empty setting = open (local/tests)."""
    owner = (get_settings().owner_telegram_id or "").strip()
    if not owner:
        return
    if not actor_telegram_id or str(actor_telegram_id).strip() != owner:
        raise HitlError("actor is not the configured owner")


def get_draft_tz(kg: KnowledgeRepository, project_id: uuid.UUID) -> Entity | None:
    artifacts = [
        e
        for e in kg.list_entities(project_id, type_="Artifact")
        if (e.payload or {}).get("kind") == "draft_tz"
    ]
    return artifacts[-1] if artifacts else None


def apply_hitl_decision(
    db: Session,
    project: Project,
    action: HitlAction,
    *,
    note: str | None = None,
    actor_telegram_id: str | None = None,
) -> HitlResult:
    """Apply owner decision. Client estimate gate runs after ``approve``."""
    assert_owner_actor(actor_telegram_id)

    if project.status != ProjectStatus.WAITING_OWNER:
        raise HitlError(
            f"project must be WAITING_OWNER for HITL, got {project.status.value}"
        )

    kg = KnowledgeRepository(db)
    draft = get_draft_tz(kg, project.id)
    if draft is None:
        raise HitlError("draft TZ not found — Discovery must finish first")

    if action == HitlAction.APPROVE:
        return _approve(db, kg, project, draft, note=note)
    if action == HitlAction.REQUEST_CHANGES:
        return _request_changes(db, kg, project, draft, note=note)
    if action == HitlAction.REJECT:
        return _reject(db, kg, project, draft, note=note)
    raise HitlError(f"unsupported HITL action: {action}")


def _approve(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
    draft: Entity,
    *,
    note: str | None,
) -> HitlResult:
    payload = dict(draft.payload or {})
    payload["review_note"] = note or "Approved by owner"
    kg.update_entity(draft, status="approved", payload=payload)

    decision = kg.create_entity(
        project_id=project.id,
        type_="Decision",
        name="Owner approved draft TZ",
        status="accepted",
        payload={
            "summary": note or "Draft TZ approved; client estimate sent for confirmation",
            "kind": "tz_approval",
            "artifact_id": str(draft.id),
            "action": HitlAction.APPROVE.value,
        },
        confidence=1.0,
    )
    kg.create_relation(
        project_id=project.id,
        from_entity_id=decision.id,
        to_entity_id=draft.id,
        type_="related_to",
        payload={"role": "approves"},
    )
    # Link requirements → approval decision (related_to, not decides —
    # so Planner can still create per-requirement Decision stubs).
    for req in kg.list_entities(project.id, type_="Requirement"):
        if req.status in {"superseded", "archived"}:
            continue
        kg.create_relation(
            project_id=project.id,
            from_entity_id=req.id,
            to_entity_id=decision.id,
            type_="related_to",
            payload={"role": "tz_gate"},
        )

    attach_client_estimate_to_draft(kg, project, draft)
    project.status = ProjectStatus.WAITING_CLIENT_ESTIMATE
    _sync_project_entity(
        kg,
        project,
        discovery_stage=DiscoveryStage.READY_FOR_OWNER.value,
        hitl=HitlAction.APPROVE.value,
    )
    db.flush()
    return HitlResult(
        project_id=project.id,
        action=HitlAction.APPROVE,
        project_status=project.status,
        artifact_id=draft.id,
        decision_id=decision.id,
        message=(
            "Draft TZ approved. Client market estimate is ready — "
            "customer must confirm before Planner."
        ),
        human_decision_required=False,
    )


def _request_changes(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
    draft: Entity,
    *,
    note: str | None,
) -> HitlResult:
    payload = dict(draft.payload or {})
    payload["review_note"] = note or "Owner requested changes"
    kg.update_entity(draft, status="changes_requested", payload=payload)

    decision = kg.create_entity(
        project_id=project.id,
        type_="Decision",
        name="Owner requested TZ changes",
        status="open",
        payload={
            "summary": note or "Changes requested before planning",
            "kind": "HumanDecisionRequired",
            "artifact_id": str(draft.id),
            "action": HitlAction.REQUEST_CHANGES.value,
        },
        confidence=1.0,
    )
    question = kg.create_entity(
        project_id=project.id,
        type_="OpenQuestion",
        name=(note or "Owner feedback")[:80],
        status="open",
        payload={
            "question": note or "Owner requested changes to the draft TZ",
            "source": "hitl",
        },
        confidence=1.0,
    )

    project.status = ProjectStatus.WAITING_CUSTOMER
    _sync_project_entity(
        kg,
        project,
        discovery_stage=DiscoveryStage.REVIEW.value,
        hitl=HitlAction.REQUEST_CHANGES.value,
    )
    db.flush()
    return HitlResult(
        project_id=project.id,
        action=HitlAction.REQUEST_CHANGES,
        project_status=project.status,
        artifact_id=draft.id,
        decision_id=decision.id,
        message=(
            f"Changes requested. Project back to WAITING_CUSTOMER "
            f"(open question {question.id})."
        ),
        human_decision_required=True,
    )


def _reject(
    db: Session,
    kg: KnowledgeRepository,
    project: Project,
    draft: Entity,
    *,
    note: str | None,
) -> HitlResult:
    payload = dict(draft.payload or {})
    payload["review_note"] = note or "Rejected by owner"
    kg.update_entity(draft, status="rejected", payload=payload)

    decision = kg.create_entity(
        project_id=project.id,
        type_="Decision",
        name="Owner rejected draft TZ",
        status="rejected",
        payload={
            "summary": note or "Draft TZ rejected",
            "kind": "HumanDecisionRequired",
            "artifact_id": str(draft.id),
            "action": HitlAction.REJECT.value,
        },
        confidence=1.0,
    )

    project.status = ProjectStatus.ARCHIVED
    _sync_project_entity(
        kg,
        project,
        discovery_stage=DiscoveryStage.READY_FOR_OWNER.value,
        hitl=HitlAction.REJECT.value,
    )
    db.flush()
    return HitlResult(
        project_id=project.id,
        action=HitlAction.REJECT,
        project_status=project.status,
        artifact_id=draft.id,
        decision_id=decision.id,
        message="Draft TZ rejected. Project archived.",
        human_decision_required=True,
    )


def _sync_project_entity(
    kg: KnowledgeRepository,
    project: Project,
    *,
    discovery_stage: str,
    hitl: str,
) -> None:
    entities = kg.list_entities(project.id, type_="Project")
    if not entities:
        return
    payload = dict(entities[0].payload or {})
    payload.update(
        {
            "status": project.status.value,
            "product_type": project.product_type,
            "discovery_stage": discovery_stage,
            "hitl_last_action": hitl,
        }
    )
    kg.update_entity(entities[0], payload=payload, name=project.name)


def owner_review_summary(db: Session, project: Project) -> dict:
    """Compact payload for Telegram owner review message."""
    kg = KnowledgeRepository(db)
    draft = get_draft_tz(kg, project.id)
    open_qs = [
        e
        for e in kg.list_entities(project.id, type_="OpenQuestion")
        if e.status == "open"
    ]
    content = (draft.payload or {}).get("content", "") if draft else ""
    preview = content[:1500] + ("…" if len(content) > 1500 else "")
    quality = evaluate_spec_quality(
        requirements=kg.list_entities(project.id, type_="Requirement"),
        open_questions=open_qs,
        risks=kg.list_entities(project.id, type_="Risk"),
    ).as_dict()
    estimate = estimate_from_artifact(draft)
    return {
        "project_id": str(project.id),
        "name": project.name,
        "status": project.status.value,
        "product_type": project.product_type,
        "artifact_id": str(draft.id) if draft else None,
        "artifact_status": draft.status if draft else None,
        "open_question_count": len(open_qs),
        "open_questions": [
            (e.payload or {}).get("question") or e.name for e in open_qs[:8]
        ],
        "draft_preview": preview,
        "quality_review": quality,
        "gaps": quality.get("gaps") or [],
        "contradictions": quality.get("contradictions") or [],
        "owner_recommendations": quality.get("owner_recommendations") or [],
        "estimate": estimate.as_dict() if estimate else None,
        "client_estimate": customer_estimate_view(
            client_estimate_from_artifact(draft),
            client_estimate_report_from_artifact(draft),
        ),
    }
