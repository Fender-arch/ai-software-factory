from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from core.models import Message, MessageKind, Project, ProjectStatus
from discovery.fsm import status_after_customer_message
from integrations.stt import get_stt_provider
from knowledge.repository import KnowledgeRepository


def create_project(
    db: Session,
    name: str,
    customer_telegram_id: str | None = None,
    product_type: str | None = None,
) -> Project:
    project = Project(
        name=name,
        status=ProjectStatus.NEW,
        customer_telegram_id=customer_telegram_id,
        product_type=product_type,
    )
    db.add(project)
    db.flush()

    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Project",
        name=name,
        payload={
            "status": project.status.value,
            "product_type": product_type,
        },
    )
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str | uuid.UUID) -> Project | None:
    try:
        pid = uuid.UUID(str(project_id))
    except ValueError:
        return None
    return db.get(Project, pid)


def ingest_text_message(
    db: Session,
    project_id: str | uuid.UUID,
    text: str,
    role: str = "customer",
) -> Message:
    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")

    message = Message(
        project_id=project.id,
        kind=MessageKind.TEXT,
        role=role,
        text=text,
        meta={},
    )
    db.add(message)
    project.status = status_after_customer_message(project.status)

    kg = KnowledgeRepository(db)
    entity = kg.create_entity(
        project_id=project.id,
        type_="Message",
        name=text[:80] or "message",
        payload={"role": role, "kind": MessageKind.TEXT.value, "text": text},
    )
    # Link message entity to project entity if present
    projects = kg.list_entities(project.id, type_="Project")
    if projects:
        kg.create_relation(
            project_id=project.id,
            from_entity_id=entity.id,
            to_entity_id=projects[0].id,
            type_="related_to",
        )

    db.commit()
    db.refresh(message)
    return message


async def ingest_voice_message(
    db: Session,
    project_id: str | uuid.UUID,
    audio: bytes,
    telegram_file_id: str | None = None,
    filename: str = "voice.ogg",
    role: str = "customer",
) -> Message:
    stt = get_stt_provider()
    transcript = await stt.transcribe(audio, filename=filename)

    project = get_project(db, project_id)
    if project is None:
        raise ValueError("project not found")

    message = Message(
        project_id=project.id,
        kind=MessageKind.VOICE,
        role=role,
        text=transcript,
        raw_file_id=telegram_file_id,
        meta={"stt_provider": stt.__class__.__name__, "filename": filename},
    )
    db.add(message)
    project.status = status_after_customer_message(project.status)

    kg = KnowledgeRepository(db)
    kg.create_entity(
        project_id=project.id,
        type_="Message",
        name=transcript[:80] or "voice-message",
        payload={
            "role": role,
            "kind": MessageKind.VOICE.value,
            "text": transcript,
            "telegram_file_id": telegram_file_id,
        },
    )

    db.commit()
    db.refresh(message)
    return message
