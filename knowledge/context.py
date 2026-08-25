"""Bounded context builder for AI Coordinator modes.

Modes must not scan the DB freely — they receive only what this module selects.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from core.coordinator import CoordinatorMode
from core.models import Entity, Message, MessageKind, Project
from knowledge.coverage import evaluate_coverage
from knowledge.repository import KnowledgeRepository
from knowledge.traceability import list_requirement_traces


def _brief(entity: Entity, *, include_payload: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(entity.id),
        "type": entity.type,
        "name": entity.name,
        "status": entity.status,
        "confidence": entity.confidence,
    }
    if include_payload:
        data["payload"] = entity.payload or {}
    return data


def _project_state(kg: KnowledgeRepository, project: Project) -> dict[str, Any]:
    entities = kg.list_entities(project.id, type_="Project")
    payload = dict(entities[0].payload) if entities else {}
    return {
        "project_id": str(project.id),
        "name": project.name,
        "status": project.status.value,
        "product_type": project.product_type,
        "discovery_stage": payload.get("discovery_stage"),
        "it_literacy": payload.get("it_literacy"),
        "kg_project_entity_id": str(entities[0].id) if entities else None,
    }


def _recent_messages(
    db: Session, project_id: uuid.UUID, *, limit: int = 12
) -> list[dict[str, Any]]:
    rows = (
        db.query(Message)
        .filter(Message.project_id == project_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "kind": m.kind.value if isinstance(m.kind, MessageKind) else str(m.kind),
            "text": m.text,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


def _entities_by_types(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    types: list[str],
    *,
    include_payload: bool = True,
    skip_archived: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {t: [] for t in types}
    for type_ in types:
        for entity in kg.list_entities(project_id, type_=type_):
            if skip_archived and entity.status == "archived":
                continue
            out[type_].append(_brief(entity, include_payload=include_payload))
    return out


class ContextBuilder:
    """Build mode-scoped dicts for ``AICoordinator.run``."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.kg = KnowledgeRepository(db)

    def build(
        self,
        mode: CoordinatorMode,
        project: Project,
        *,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        builders = {
            CoordinatorMode.DISCOVERY: self._discovery,
            CoordinatorMode.REVIEWER: self._reviewer,
            CoordinatorMode.ARCHITECT: self._architect,
            CoordinatorMode.PLANNER: self._planner,
            CoordinatorMode.DEVELOPER: self._developer,
            CoordinatorMode.QA: self._qa,
        }
        context = builders[mode](project)
        if extra:
            context = {**context, **extra}
        context["mode"] = mode.value
        return context

    def _discovery(self, project: Project) -> dict[str, Any]:
        state = _project_state(self.kg, project)
        buckets = _entities_by_types(
            self.kg,
            project.id,
            ["Requirement", "OpenQuestion", "Risk"],
        )
        return {
            **state,
            "recent_messages": _recent_messages(self.db, project.id, limit=10),
            "requirements": buckets["Requirement"],
            "open_questions": buckets["OpenQuestion"],
            "risks": buckets["Risk"],
            "requirement_count": len(buckets["Requirement"]),
            "open_question_count": len(
                [q for q in buckets["OpenQuestion"] if q["status"] == "open"]
            ),
            "coverage": evaluate_coverage(
                self.kg, project.id, product_type=project.product_type
            ).as_dict(),
        }

    def _reviewer(self, project: Project) -> dict[str, Any]:
        state = _project_state(self.kg, project)
        buckets = _entities_by_types(
            self.kg,
            project.id,
            ["Requirement", "OpenQuestion", "Risk", "Artifact", "Decision"],
        )
        draft_tz = [
            a
            for a in buckets["Artifact"]
            if (a.get("payload") or {}).get("kind") == "draft_tz"
        ]
        return {
            **state,
            "requirements": buckets["Requirement"],
            "open_questions": buckets["OpenQuestion"],
            "risks": buckets["Risk"],
            "decisions": buckets["Decision"],
            "draft_tz": draft_tz[-1] if draft_tz else None,
            "coverage": evaluate_coverage(
                self.kg, project.id, product_type=project.product_type
            ).as_dict(),
            "traces": list_requirement_traces(self.kg, project.id),
        }

    def _architect(self, project: Project) -> dict[str, Any]:
        state = _project_state(self.kg, project)
        buckets = _entities_by_types(
            self.kg,
            project.id,
            ["Requirement", "Decision", "Risk", "OpenQuestion"],
        )
        return {
            **state,
            "requirements": buckets["Requirement"],
            "decisions": buckets["Decision"],
            "risks": buckets["Risk"],
            "open_questions": [
                q for q in buckets["OpenQuestion"] if q["status"] == "open"
            ],
            "coverage": evaluate_coverage(
                self.kg, project.id, product_type=project.product_type
            ).as_dict(),
        }

    def _planner(self, project: Project) -> dict[str, Any]:
        state = _project_state(self.kg, project)
        buckets = _entities_by_types(
            self.kg,
            project.id,
            ["Requirement", "Decision", "Task", "Artifact"],
        )
        return {
            **state,
            "requirements": buckets["Requirement"],
            "decisions": buckets["Decision"],
            "tasks": buckets["Task"],
            "artifacts": buckets["Artifact"],
            "traces": list_requirement_traces(self.kg, project.id),
        }

    def _developer(self, project: Project) -> dict[str, Any]:
        state = _project_state(self.kg, project)
        buckets = _entities_by_types(
            self.kg,
            project.id,
            ["Task", "Requirement", "Decision"],
        )
        return {
            **state,
            "tasks": buckets["Task"],
            "requirements": buckets["Requirement"],
            "decisions": buckets["Decision"],
            "traces": list_requirement_traces(self.kg, project.id),
        }

    def _qa(self, project: Project) -> dict[str, Any]:
        state = _project_state(self.kg, project)
        buckets = _entities_by_types(
            self.kg,
            project.id,
            ["Task", "Requirement", "Artifact"],
        )
        return {
            **state,
            "tasks": buckets["Task"],
            "requirements": buckets["Requirement"],
            "artifacts": buckets["Artifact"],
            "coverage": evaluate_coverage(
                self.kg, project.id, product_type=project.product_type
            ).as_dict(),
        }


def build_mode_context(
    db: Session,
    mode: CoordinatorMode,
    project: Project,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ContextBuilder(db).build(mode, project, extra=extra)
