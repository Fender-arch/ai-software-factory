"""Owner TZ console mutations: requirement status, links, history."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.models import Entity, Project, ProjectStatus
from discovery.tz_outline import topic_by_id
from knowledge.history import list_entity_history, record_entity_event
from knowledge.repository import KnowledgeRepository
from knowledge.tz_graph import UNSCOPED_STAGE_ID, UNSCOPED_TOPIC_ID
from knowledge.types import (
    CONFLICT_LOCKED_STATUSES,
    REQUIREMENT_LINK_TYPES,
    REQUIREMENT_STATUSES,
    normalize_requirement_status,
)


REQUIREMENT_PRIORITIES = frozenset({"must", "should", "could"})
HISTORY_SNIPPET = 360


class ConsoleError(ValueError):
    """Domain error for owner console operations."""


def list_console_projects(db: Session) -> list[Project]:
    return list(db.query(Project).order_by(Project.created_at.desc()).all())


def _require_requirement(
    kg: KnowledgeRepository, project_id: uuid.UUID, entity_id: uuid.UUID
) -> Entity:
    entity = kg.get_entity(entity_id, project_id=project_id)
    if entity is None or entity.type != "Requirement":
        raise ConsoleError("requirement not found")
    if entity.status == "archived":
        raise ConsoleError("requirement is archived")
    return entity


def _history_row(row) -> dict[str, Any]:
    created = row.created_at
    return {
        "id": str(row.id),
        "actor": row.actor,
        "action": row.action,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "reason": row.reason,
        "payload": row.payload or {},
        "created_at": created.isoformat() if isinstance(created, datetime) else created,
    }


def requirement_card(
    db: Session, project: Project, requirement_id: uuid.UUID
) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    entity = _require_requirement(kg, project.id, requirement_id)
    payload = dict(entity.payload or {})
    display = normalize_requirement_status(entity.status)
    neighbors = kg.neighbors(project.id, entity.id, direction="both")
    links: list[dict[str, Any]] = []
    for rel, other in neighbors:
        if rel.type in REQUIREMENT_LINK_TYPES and other.type == "Requirement":
            direction = "out" if rel.from_entity_id == entity.id else "in"
            links.append(
                {
                    "id": str(rel.id),
                    "type": rel.type,
                    "kind": rel.type,
                    "peer_id": str(other.id),
                    "peer_name": other.name,
                    "direction": direction,
                }
            )
        elif rel.type not in REQUIREMENT_LINK_TYPES:
            direction = "out" if rel.from_entity_id == entity.id else "in"
            links.append(
                {
                    "id": str(rel.id),
                    "type": rel.type,
                    "kind": "other",
                    "peer_id": str(other.id),
                    "peer_name": other.name,
                    "peer_type": other.type,
                    "direction": direction,
                }
            )

    topic_id = payload.get("topic_id")
    stage = payload.get("stage")
    return {
        "id": str(entity.id),
        "name": entity.name,
        "description": payload.get("description") or entity.name,
        "status": display,
        "reason": payload.get("status_reason"),
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "author": {
            "role": payload.get("author_role"),
            "id": payload.get("author_id"),
        },
        "topic_id": topic_id,
        "stage": stage,
        "priority": payload.get("priority"),
        "links": links,
        "history": [
            _history_row(h) for h in list_entity_history(db, entity.id, project_id=project.id)
        ],
    }


def _snippet(value: str | None) -> str:
    text = str(value or "")
    if len(text) <= HISTORY_SNIPPET:
        return text
    return text[: HISTORY_SNIPPET - 1] + "…"


def _requirement_name(topic_id: str, description: str) -> str:
    body = (description or "").strip().replace("\n", " ")
    return f"{topic_id}: {body[:60]}" if body else topic_id


def _resolve_topic(topic_id: str | None) -> tuple[str, str]:
    raw = (topic_id or "").strip()
    if not raw:
        raise ConsoleError("topic_id is required")
    topic = topic_by_id(raw)
    if topic is not None:
        return topic.id, topic.stage.value
    if raw in {UNSCOPED_TOPIC_ID, "other"}:
        return UNSCOPED_TOPIC_ID, UNSCOPED_STAGE_ID
    raise ConsoleError(f"unknown topic_id: {raw}")


def create_requirement(
    db: Session,
    project: Project,
    *,
    description: str,
    topic_id: str,
    priority: str | None = None,
    actor: str = "console",
) -> dict[str, Any]:
    text = (description or "").strip()
    if not text:
        raise ConsoleError("description is required")
    prio = (priority or "should").strip()
    if prio not in REQUIREMENT_PRIORITIES:
        raise ConsoleError(f"unsupported priority: {prio}")
    resolved_topic, stage = _resolve_topic(topic_id)

    kg = KnowledgeRepository(db)
    entity = kg.create_entity(
        project_id=project.id,
        type_="Requirement",
        name=_requirement_name(resolved_topic, text),
        status="new",
        payload={
            "title": resolved_topic,
            "description": text,
            "priority": prio,
            "stage": stage,
            "topic_id": resolved_topic,
            "product_type": project.product_type,
            "acceptance_criteria": [],
            "author_role": "console",
            "author_id": actor,
        },
        confidence=1.0,
    )
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=entity.id,
        actor=actor,
        action="created",
        to_status="new",
        payload={"topic_id": resolved_topic, "stage": stage, "source": "console"},
    )
    db.flush()
    return requirement_card(db, project, entity.id)


def update_requirement(
    db: Session,
    project: Project,
    requirement_id: uuid.UUID,
    *,
    description: str | None = None,
    topic_id: str | None = None,
    priority: str | None = None,
    actor: str = "console",
) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    entity = _require_requirement(kg, project.id, requirement_id)
    payload = dict(entity.payload or {})
    fields: dict[str, dict[str, str | None]] = {}

    if description is not None:
        text = description.strip()
        if not text:
            raise ConsoleError("description is required")
        previous = str(payload.get("description") or entity.name or "")
        if text != previous:
            fields["description"] = {"from": _snippet(previous), "to": _snippet(text)}
            payload["description"] = text
            entity_name = _requirement_name(
                str(payload.get("topic_id") or topic_id or "req"), text
            )
        else:
            entity_name = None
    else:
        entity_name = None

    if topic_id is not None:
        resolved_topic, stage = _resolve_topic(topic_id)
        previous_topic = str(payload.get("topic_id") or "")
        if resolved_topic != previous_topic:
            fields["topic_id"] = {"from": previous_topic or None, "to": resolved_topic}
            payload["topic_id"] = resolved_topic
            payload["title"] = resolved_topic
            payload["stage"] = stage
            desc = str(payload.get("description") or "")
            entity_name = _requirement_name(resolved_topic, desc)

    if priority is not None:
        prio = priority.strip()
        if prio not in REQUIREMENT_PRIORITIES:
            raise ConsoleError(f"unsupported priority: {prio}")
        previous_prio = str(payload.get("priority") or "")
        if prio != previous_prio:
            fields["priority"] = {"from": previous_prio or None, "to": prio}
            payload["priority"] = prio

    if not fields:
        return requirement_card(db, project, requirement_id)

    kg.update_entity(entity, name=entity_name, payload=payload)
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=entity.id,
        actor=actor,
        action="updated",
        payload={"fields": fields},
    )
    db.flush()
    return requirement_card(db, project, requirement_id)


def set_requirement_status(
    db: Session,
    project: Project,
    requirement_id: uuid.UUID,
    status: str,
    *,
    reason: str | None = None,
    actor: str = "console",
) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    entity = _require_requirement(kg, project.id, requirement_id)
    target = (status or "").strip()
    if target not in REQUIREMENT_STATUSES:
        raise ConsoleError(f"unsupported status: {target}")
    if target == "rejected" and not (reason or "").strip():
        raise ConsoleError("rejected status requires a reason")

    previous = normalize_requirement_status(entity.status)
    payload = dict(entity.payload or {})
    if (reason or "").strip():
        payload["status_reason"] = reason.strip()
    elif target != "rejected":
        payload.pop("status_reason", None)

    kg.update_entity(entity, status=target, payload=payload)
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=entity.id,
        actor=actor,
        action="status_change",
        from_status=previous,
        to_status=target,
        reason=(reason or "").strip() or None,
    )
    db.flush()
    return requirement_card(db, project, requirement_id)


def _has_conflict_link(
    kg: KnowledgeRepository, project_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    for rel, other in kg.neighbors(
        project_id, entity_id, relation_type="conflicts_with", direction="both"
    ):
        if other.type == "Requirement" and other.status != "archived":
            return True
        _ = rel
    return False


def _previous_non_conflict_status(db: Session, entity: Entity) -> str:
    history = list_entity_history(db, entity.id, project_id=entity.project_id)
    for row in reversed(history):
        candidate = row.to_status or row.from_status
        if not candidate:
            continue
        mapped = normalize_requirement_status(candidate)
        if mapped != "conflict" and mapped in REQUIREMENT_STATUSES:
            return mapped
    return "processed"


def _apply_conflict_status(
    db: Session, kg: KnowledgeRepository, entity: Entity, *, actor: str
) -> None:
    current = normalize_requirement_status(entity.status)
    if current in CONFLICT_LOCKED_STATUSES or current == "conflict":
        return
    payload = dict(entity.payload or {})
    kg.update_entity(entity, status="conflict", payload=payload)
    record_entity_event(
        db,
        project_id=entity.project_id,
        entity_id=entity.id,
        actor=actor,
        action="status_change",
        from_status=current,
        to_status="conflict",
        payload={"auto": True, "from": "conflicts_with"},
    )


def _restore_after_conflict_cleared(
    db: Session, kg: KnowledgeRepository, entity: Entity, *, actor: str
) -> None:
    if _has_conflict_link(kg, entity.project_id, entity.id):
        return
    current = normalize_requirement_status(entity.status)
    if current != "conflict":
        return
    restored = _previous_non_conflict_status(db, entity)
    payload = dict(entity.payload or {})
    kg.update_entity(entity, status=restored, payload=payload)
    record_entity_event(
        db,
        project_id=entity.project_id,
        entity_id=entity.id,
        actor=actor,
        action="status_change",
        from_status="conflict",
        to_status=restored,
        payload={"auto": True, "from": "conflicts_with_cleared"},
    )


def add_requirement_relation(
    db: Session,
    project: Project,
    requirement_id: uuid.UUID,
    *,
    rel_type: str,
    peer_id: uuid.UUID,
    actor: str = "console",
) -> dict[str, Any]:
    if rel_type not in REQUIREMENT_LINK_TYPES:
        raise ConsoleError(f"unsupported relation type: {rel_type}")
    kg = KnowledgeRepository(db)
    src = _require_requirement(kg, project.id, requirement_id)
    dst = _require_requirement(kg, project.id, peer_id)
    if src.id == dst.id:
        raise ConsoleError("relation cannot be reflexive")

    existing = kg.list_relations(
        project.id, type_=rel_type, from_entity_id=src.id, to_entity_id=dst.id
    )
    if rel_type == "conflicts_with":
        existing += kg.list_relations(
            project.id, type_=rel_type, from_entity_id=dst.id, to_entity_id=src.id
        )
    if existing:
        raise ConsoleError("relation already exists")

    rel = kg.create_relation(
        project_id=project.id,
        from_entity_id=src.id,
        to_entity_id=dst.id,
        type_=rel_type,
        payload={"source": "console"},
    )
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=src.id,
        actor=actor,
        action="relation_add",
        payload={"relation_id": str(rel.id), "type": rel_type, "peer_id": str(dst.id)},
    )
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=dst.id,
        actor=actor,
        action="relation_add",
        payload={
            "relation_id": str(rel.id),
            "type": rel_type,
            "peer_id": str(src.id),
            "inbound": True,
        },
    )
    if rel_type == "conflicts_with":
        _apply_conflict_status(db, kg, src, actor=actor)
        _apply_conflict_status(db, kg, dst, actor=actor)
    db.flush()
    return requirement_card(db, project, requirement_id)


def delete_requirement_relation(
    db: Session,
    project: Project,
    relation_id: uuid.UUID,
    *,
    actor: str = "console",
) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    rel = kg.get_relation(relation_id, project_id=project.id)
    if rel is None or rel.type not in REQUIREMENT_LINK_TYPES:
        raise ConsoleError("relation not found")
    src_id = rel.from_entity_id
    dst_id = rel.to_entity_id
    rel_type = rel.type
    kg.delete_relation(rel)
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=src_id,
        actor=actor,
        action="relation_remove",
        payload={"relation_id": str(relation_id), "type": rel_type, "peer_id": str(dst_id)},
    )
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=dst_id,
        actor=actor,
        action="relation_remove",
        payload={
            "relation_id": str(relation_id),
            "type": rel_type,
            "peer_id": str(src_id),
            "inbound": True,
        },
    )
    if rel_type == "conflicts_with":
        src = kg.get_entity(src_id, project_id=project.id)
        dst = kg.get_entity(dst_id, project_id=project.id)
        if src is not None:
            _restore_after_conflict_cleared(db, kg, src, actor=actor)
        if dst is not None:
            _restore_after_conflict_cleared(db, kg, dst, actor=actor)
    db.flush()
    return requirement_card(db, project, src_id)


def serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "status": project.status.value,
        "product_type": project.product_type,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


def set_console_project_status(
    db: Session,
    project: Project,
    status: str,
    *,
    reason: str | None = None,
    actor: str = "console",
) -> dict[str, Any]:
    """Owner override of ``projects.status``. Allows any known ProjectStatus."""
    target = (status or "").strip()
    try:
        new_status = ProjectStatus(target)
    except ValueError as exc:
        raise ConsoleError(f"unsupported project status: {target}") from exc

    previous = project.status
    if previous == new_status:
        return serialize_project(project)

    project.status = new_status
    kg = KnowledgeRepository(db)
    entities = kg.list_entities(project.id, type_="Project")
    if entities:
        ent = entities[0]
        payload = dict(ent.payload or {})
        payload["status"] = new_status.value
        kg.update_entity(ent, payload=payload)
        record_entity_event(
            db,
            project_id=project.id,
            entity_id=ent.id,
            actor=actor,
            action="status_change",
            from_status=previous.value,
            to_status=new_status.value,
            reason=(reason or "").strip() or None,
            payload={"kind": "project_status", "override": True},
        )
    db.flush()
    return serialize_project(project)
