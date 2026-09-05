"""Approved MVP requirement slice (in_mvp / must / scope_in)."""

from __future__ import annotations

from typing import Any, Iterable

from core.models import Entity
from knowledge.repository import KnowledgeRepository

EXCLUDED_STATUSES = frozenset(
    {"superseded", "archived", "rejected"}
)


def _payload(entity: Entity) -> dict[str, Any]:
    return dict(entity.payload or {})


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "in", "mvp"}
    return False


def is_scope_in(entity: Entity) -> bool:
    payload = _payload(entity)
    if "scope_in" in payload:
        return _truthy(payload.get("scope_in"))
    scope = str(payload.get("scope") or "").strip().lower()
    return scope in {"in", "scope_in", "mvp"}


def is_explicit_in_mvp(entity: Entity) -> bool:
    return _truthy(_payload(entity).get("in_mvp"))


def active_requirements(entities: Iterable[Entity]) -> list[Entity]:
    return [
        e
        for e in entities
        if e.type == "Requirement" and e.status not in EXCLUDED_STATUSES
    ]


def select_mvp_requirements(requirements: Iterable[Entity]) -> list[Entity]:
    """Pick the approved MVP cut without inventing extra product scope.

    Order: explicit ``in_mvp`` → ``scope_in`` / ``scope=in`` → ``priority=must``
    → remaining active requirements.
    """
    active = active_requirements(requirements)
    explicit = [e for e in active if is_explicit_in_mvp(e)]
    if explicit:
        return explicit
    scoped = [e for e in active if is_scope_in(e)]
    if scoped:
        return scoped
    must = [
        e
        for e in active
        if str(_payload(e).get("priority") or "should").lower() == "must"
    ]
    if must:
        return must
    return active


def mark_in_mvp(
    kg: KnowledgeRepository,
    selected: Iterable[Entity],
    all_requirements: Iterable[Entity],
) -> list[Entity]:
    """Persist a minimal ``payload.in_mvp`` flag on the chosen slice."""
    chosen_ids = {e.id for e in selected}
    marked: list[Entity] = []
    for entity in all_requirements:
        if entity.status in EXCLUDED_STATUSES:
            continue
        payload = _payload(entity)
        flag = entity.id in chosen_ids
        if payload.get("in_mvp") is flag:
            if flag:
                marked.append(entity)
            continue
        payload["in_mvp"] = flag
        kg.update_entity(entity, payload=payload)
        if flag:
            marked.append(entity)
    return marked
