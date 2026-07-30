from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from core.models import Entity, Relation


class KnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_entity(
        self,
        project_id: uuid.UUID,
        type_: str,
        name: str,
        payload: dict | None = None,
        status: str = "active",
        confidence: float | None = None,
    ) -> Entity:
        entity = Entity(
            project_id=project_id,
            type=type_,
            name=name,
            payload=payload or {},
            status=status,
            confidence=confidence,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def create_relation(
        self,
        project_id: uuid.UUID,
        from_entity_id: uuid.UUID,
        to_entity_id: uuid.UUID,
        type_: str,
        payload: dict | None = None,
    ) -> Relation:
        relation = Relation(
            project_id=project_id,
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            type=type_,
            payload=payload or {},
        )
        self.db.add(relation)
        self.db.flush()
        return relation

    def list_entities(self, project_id: uuid.UUID, type_: str | None = None) -> list[Entity]:
        q = self.db.query(Entity).filter(Entity.project_id == project_id)
        if type_:
            q = q.filter(Entity.type == type_)
        return list(q.order_by(Entity.created_at.asc()).all())
