"""Canonical MVP entity and relation type names (see docs/09-Knowledge-Graph.md)."""

from __future__ import annotations

from typing import Final

ENTITY_TYPES: Final[frozenset[str]] = frozenset(
    {
        "Project",
        "Message",
        "Requirement",
        "OpenQuestion",
        "Decision",
        "Task",
        "Artifact",
        "Risk",
        "Feedback",
    }
)

RELATION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "derived_from",
        "decides",
        "implements",
        "blocks",
        "related_to",
        "depends_on",
        "conflicts_with",
    }
)

REQUIREMENT_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "new",
        "processed",
        "needs_clarification",
        "conflict",
        "rejected",
        "superseded",
    }
)

REQUIREMENT_LINK_TYPES: Final[frozenset[str]] = frozenset({"depends_on", "conflicts_with"})

HISTORY_ACTORS: Final[frozenset[str]] = frozenset({"discovery", "console", "system"})
HISTORY_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "created",
        "updated",
        "deleted",
        "status_change",
        "relation_add",
        "relation_remove",
    }
)

# Statuses that are not auto-overwritten when marking a conflict.
CONFLICT_LOCKED_STATUSES: Final[frozenset[str]] = frozenset({"rejected", "superseded"})


def normalize_requirement_status(status: str | None) -> str:
    """Map stored entity.status to console Requirement status."""
    raw = (status or "").strip() or "new"
    if raw == "active":
        return "new"
    if raw in REQUIREMENT_STATUSES:
        return raw
    if raw == "archived":
        return "archived"
    return "new"


# Preferred forward spine: Message → Requirement → Decision → Task → Artifact
TRACE_HOPS: Final[tuple[tuple[str, str, str], ...]] = (
    ("Message", "derived_from", "Requirement"),
    ("Requirement", "decides", "Decision"),
    ("Decision", "implements", "Task"),
    ("Task", "related_to", "Artifact"),
)
