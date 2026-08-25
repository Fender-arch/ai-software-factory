"""Append-only entity history (audit log, not an event bus)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.models import EntityHistory

log = logging.getLogger(__name__)


def record_entity_event(
    db: Session,
    *,
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    actor: str,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    reason: str | None = None,
    payload: dict | None = None,
) -> EntityHistory | None:
    """Write an audit row. Missing schema must not fail Discovery."""
    try:
        with db.begin_nested():
            row = EntityHistory(
                project_id=project_id,
                entity_id=entity_id,
                actor=actor,
                action=action,
                from_status=from_status,
                to_status=to_status,
                reason=reason,
                payload=payload or {},
            )
            db.add(row)
            db.flush()
            return row
    except SQLAlchemyError:
        log.exception("entity_history write failed; Discovery continues")
        return None


def list_entity_history(
    db: Session,
    entity_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> list[EntityHistory]:
    q = db.query(EntityHistory).filter(EntityHistory.entity_id == entity_id)
    if project_id is not None:
        q = q.filter(EntityHistory.project_id == project_id)
    return list(q.order_by(EntityHistory.created_at.asc()).all())
