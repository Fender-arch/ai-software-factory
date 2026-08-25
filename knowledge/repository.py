from __future__ import annotations

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.models import Entity, Relation
from knowledge.types import ENTITY_TYPES, RELATION_TYPES


class KnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Entity CRUD ---------------------------------------------------------

    def create_entity(
        self,
        project_id: uuid.UUID,
        type_: str,
        name: str,
        payload: dict | None = None,
        status: str = "active",
        confidence: float | None = None,
        *,
        validate_type: bool = True,
    ) -> Entity:
        if validate_type and type_ not in ENTITY_TYPES:
            raise ValueError(f"unsupported entity type: {type_}")
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

    def get_entity(
        self, entity_id: uuid.UUID, *, project_id: uuid.UUID | None = None
    ) -> Entity | None:
        entity = self.db.get(Entity, entity_id)
        if entity is None:
            return None
        if project_id is not None and entity.project_id != project_id:
            return None
        return entity

    def list_entities(
        self,
        project_id: uuid.UUID,
        type_: str | None = None,
        *,
        status: str | None = None,
    ) -> list[Entity]:
        q = self.db.query(Entity).filter(Entity.project_id == project_id)
        if type_:
            q = q.filter(Entity.type == type_)
        if status is not None:
            q = q.filter(Entity.status == status)
        return list(q.order_by(Entity.created_at.asc()).all())

    def update_entity(
        self,
        entity: Entity,
        *,
        name: str | None = None,
        payload: dict | None = None,
        status: str | None = None,
        confidence: float | None = None,
    ) -> Entity:
        if name is not None:
            entity.name = name
        if payload is not None:
            entity.payload = payload
        if status is not None:
            entity.status = status
        if confidence is not None:
            entity.confidence = confidence
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete_entity(self, entity: Entity, *, soft: bool = True) -> None:
        """Soft-delete sets status=archived; hard-delete cascades relations via FK."""
        if soft:
            entity.status = "archived"
            self.db.add(entity)
            self.db.flush()
            return
        self.db.delete(entity)
        self.db.flush()

    def search_entities(
        self,
        project_id: uuid.UUID,
        query: str,
        *,
        type_: str | None = None,
        limit: int = 50,
    ) -> list[Entity]:
        """Basic name/payload substring search (MVP; no full-text index yet)."""
        needle = (query or "").strip()
        if not needle:
            return []
        pattern = f"%{needle}%"
        q = self.db.query(Entity).filter(Entity.project_id == project_id)
        if type_:
            q = q.filter(Entity.type == type_)
        # SQLite JSON is stored as text via JSON variant; cast name + payload string.
        q = q.filter(
            or_(
                Entity.name.ilike(pattern),
                Entity.status.ilike(pattern),
            )
        )
        matches = list(q.order_by(Entity.created_at.asc()).limit(limit).all())
        # Also scan payload in Python for portability across SQLite/Postgres.
        if len(matches) < limit:
            seen = {e.id for e in matches}
            lowered = needle.lower()
            for entity in self.list_entities(project_id, type_=type_):
                if entity.id in seen:
                    continue
                blob = str(entity.payload or {}).lower()
                if lowered in blob or lowered in entity.name.lower():
                    matches.append(entity)
                    seen.add(entity.id)
                if len(matches) >= limit:
                    break
        return matches[:limit]

    # --- Relation CRUD -------------------------------------------------------

    def create_relation(
        self,
        project_id: uuid.UUID,
        from_entity_id: uuid.UUID,
        to_entity_id: uuid.UUID,
        type_: str,
        payload: dict | None = None,
        *,
        validate_type: bool = True,
    ) -> Relation:
        if validate_type and type_ not in RELATION_TYPES:
            raise ValueError(f"unsupported relation type: {type_}")
        if from_entity_id == to_entity_id:
            raise ValueError("relation cannot be reflexive")
        src = self.get_entity(from_entity_id, project_id=project_id)
        dst = self.get_entity(to_entity_id, project_id=project_id)
        if src is None or dst is None:
            raise ValueError("relation endpoints must belong to the project")
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

    def get_relation(
        self, relation_id: uuid.UUID, *, project_id: uuid.UUID | None = None
    ) -> Relation | None:
        relation = self.db.get(Relation, relation_id)
        if relation is None:
            return None
        if project_id is not None and relation.project_id != project_id:
            return None
        return relation

    def list_relations(
        self,
        project_id: uuid.UUID,
        *,
        type_: str | None = None,
        from_entity_id: uuid.UUID | None = None,
        to_entity_id: uuid.UUID | None = None,
    ) -> list[Relation]:
        q = self.db.query(Relation).filter(Relation.project_id == project_id)
        if type_:
            q = q.filter(Relation.type == type_)
        if from_entity_id is not None:
            q = q.filter(Relation.from_entity_id == from_entity_id)
        if to_entity_id is not None:
            q = q.filter(Relation.to_entity_id == to_entity_id)
        return list(q.order_by(Relation.created_at.asc()).all())

    def delete_relation(self, relation: Relation) -> None:
        self.db.delete(relation)
        self.db.flush()

    def neighbors(
        self,
        project_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        relation_type: str | None = None,
        direction: str = "both",
    ) -> list[tuple[Relation, Entity]]:
        """Return (relation, other_entity) pairs for an entity."""
        if direction not in {"out", "in", "both"}:
            raise ValueError("direction must be 'out', 'in', or 'both'")
        results: list[tuple[Relation, Entity]] = []
        if direction in {"out", "both"}:
            for rel in self.list_relations(
                project_id, type_=relation_type, from_entity_id=entity_id
            ):
                other = self.get_entity(rel.to_entity_id, project_id=project_id)
                if other is not None:
                    results.append((rel, other))
        if direction in {"in", "both"}:
            for rel in self.list_relations(
                project_id, type_=relation_type, to_entity_id=entity_id
            ):
                other = self.get_entity(rel.from_entity_id, project_id=project_id)
                if other is not None:
                    results.append((rel, other))
        return results
