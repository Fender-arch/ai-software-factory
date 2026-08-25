"""Traceability helpers: Message → Requirement → Decision → Task → Artifact."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from core.models import Entity, Relation
from knowledge.repository import KnowledgeRepository
from knowledge.types import TRACE_HOPS


@dataclass
class TraceHop:
    relation: Relation
    entity: Entity


@dataclass
class TraceChain:
    """Ordered entities along the preferred spine, starting at ``root``."""

    root: Entity
    hops: list[TraceHop] = field(default_factory=list)

    @property
    def entities(self) -> list[Entity]:
        return [self.root, *[h.entity for h in self.hops]]

    def of_type(self, type_: str) -> list[Entity]:
        return [e for e in self.entities if e.type == type_]

    def as_dict(self) -> dict:
        return {
            "root": _entity_brief(self.root),
            "chain": [
                {
                    "relation_type": hop.relation.type,
                    "relation_id": str(hop.relation.id),
                    "entity": _entity_brief(hop.entity),
                }
                for hop in self.hops
            ],
            "types": [e.type for e in self.entities],
        }


def _entity_brief(entity: Entity) -> dict:
    return {
        "id": str(entity.id),
        "type": entity.type,
        "name": entity.name,
        "status": entity.status,
    }


def link_derived_from(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    message_id: uuid.UUID,
    requirement_or_other_id: uuid.UUID,
    *,
    payload: dict | None = None,
) -> Relation:
    return kg.create_relation(
        project_id=project_id,
        from_entity_id=message_id,
        to_entity_id=requirement_or_other_id,
        type_="derived_from",
        payload=payload,
    )


def link_decides(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    decision_id: uuid.UUID,
    *,
    payload: dict | None = None,
) -> Relation:
    return kg.create_relation(
        project_id=project_id,
        from_entity_id=requirement_id,
        to_entity_id=decision_id,
        type_="decides",
        payload=payload,
    )


def link_implements(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    decision_id: uuid.UUID,
    task_id: uuid.UUID,
    *,
    payload: dict | None = None,
) -> Relation:
    return kg.create_relation(
        project_id=project_id,
        from_entity_id=decision_id,
        to_entity_id=task_id,
        type_="implements",
        payload=payload,
    )


def link_task_artifact(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    artifact_id: uuid.UUID,
    *,
    payload: dict | None = None,
) -> Relation:
    return kg.create_relation(
        project_id=project_id,
        from_entity_id=task_id,
        to_entity_id=artifact_id,
        type_="related_to",
        payload=payload or {"role": "produced_by_task"},
    )


def ensure_decision_for_requirement(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    requirement: Entity,
    *,
    name: str | None = None,
    payload: dict | None = None,
) -> Entity:
    """Idempotent: reuse existing Decision linked via ``decides``, else create one."""
    for rel, other in kg.neighbors(
        project_id, requirement.id, relation_type="decides", direction="out"
    ):
        if other.type == "Decision" and other.status != "archived":
            return other
    decision = kg.create_entity(
        project_id=project_id,
        type_="Decision",
        name=name or f"Decision: {requirement.name[:60]}",
        status="proposed",
        payload=payload
        or {
            "summary": (requirement.payload or {}).get("description", requirement.name),
            "requirement_id": str(requirement.id),
        },
        confidence=requirement.confidence,
    )
    link_decides(kg, project_id, requirement.id, decision.id)
    return decision


def ensure_task_for_decision(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    decision: Entity,
    *,
    name: str | None = None,
    payload: dict | None = None,
) -> Entity:
    """Idempotent: reuse existing Task linked via ``implements``, else create one."""
    for rel, other in kg.neighbors(
        project_id, decision.id, relation_type="implements", direction="out"
    ):
        if other.type == "Task" and other.status != "archived":
            return other
    task = kg.create_entity(
        project_id=project_id,
        type_="Task",
        name=name or f"Implement: {decision.name[:60]}",
        status="NEW",
        payload=payload
        or {
            "title": name or decision.name,
            "description": (decision.payload or {}).get("summary", ""),
            "acceptance_criteria": [],
            "decision_id": str(decision.id),
        },
    )
    link_implements(kg, project_id, decision.id, task.id)
    return task


def build_trace_forward(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    root: Entity,
    *,
    max_hops: int = 8,
) -> TraceChain:
    """Follow preferred TRACE_HOPS forward from ``root`` (greedy first match)."""
    chain = TraceChain(root=root)
    current = root
    for _ in range(max_hops):
        hop_def = next((h for h in TRACE_HOPS if h[0] == current.type), None)
        if hop_def is None:
            break
        _src_type, rel_type, dst_type = hop_def
        nxt: Entity | None = None
        chosen_rel: Relation | None = None
        for rel, other in kg.neighbors(
            project_id, current.id, relation_type=rel_type, direction="out"
        ):
            if other.type == dst_type and other.status != "archived":
                nxt = other
                chosen_rel = rel
                break
        if nxt is None or chosen_rel is None:
            break
        chain.hops.append(TraceHop(relation=chosen_rel, entity=nxt))
        current = nxt
    return chain


def build_trace_to_task(
    kg: KnowledgeRepository,
    project_id: uuid.UUID,
    *,
    message_id: uuid.UUID | None = None,
    requirement_id: uuid.UUID | None = None,
) -> TraceChain | None:
    """Build Message→Requirement→Decision→Task chain, creating Decision/Task stubs."""
    if message_id is not None:
        message = kg.get_entity(message_id, project_id=project_id)
        if message is None or message.type != "Message":
            return None
        req: Entity | None = None
        for _rel, other in kg.neighbors(
            project_id, message.id, relation_type="derived_from", direction="out"
        ):
            if other.type == "Requirement" and other.status != "archived":
                req = other
                break
        if req is None:
            return build_trace_forward(kg, project_id, message)
        decision = ensure_decision_for_requirement(kg, project_id, req)
        ensure_task_for_decision(kg, project_id, decision)
        return build_trace_forward(kg, project_id, message)

    if requirement_id is not None:
        req = kg.get_entity(requirement_id, project_id=project_id)
        if req is None or req.type != "Requirement":
            return None
        decision = ensure_decision_for_requirement(kg, project_id, req)
        ensure_task_for_decision(kg, project_id, decision)
        return build_trace_forward(kg, project_id, req)

    return None


def list_requirement_traces(
    kg: KnowledgeRepository, project_id: uuid.UUID
) -> list[dict]:
    """Coverage/search helper: each Requirement with upstream messages and downstream tasks."""
    out: list[dict] = []
    for req in kg.list_entities(project_id, type_="Requirement"):
        if req.status == "archived":
            continue
        messages = [
            _entity_brief(other)
            for _rel, other in kg.neighbors(
                project_id, req.id, relation_type="derived_from", direction="in"
            )
            if other.type == "Message"
        ]
        forward = build_trace_forward(kg, project_id, req)
        out.append(
            {
                "requirement": _entity_brief(req),
                "messages": messages,
                "decisions": [_entity_brief(e) for e in forward.of_type("Decision")],
                "tasks": [_entity_brief(e) for e in forward.of_type("Task")],
                "artifacts": [_entity_brief(e) for e in forward.of_type("Artifact")],
                "chain_types": forward.as_dict()["types"],
            }
        )
    return out
