"""Project file attachments for the owner TZ console (DEC-007)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import Entity, Message, Project
from discovery.fsm import DiscoveryStage, parse_stage
from knowledge.history import list_entity_history, record_entity_event
from knowledge.repository import KnowledgeRepository
from knowledge.tz_graph import STAGE_LABELS_RU, UNSCOPED_STAGE_ID

UPLOADED_KIND = "uploaded_file"
DEFAULT_MAX_BYTES = 20 * 1024 * 1024


class FileError(ValueError):
    """Domain error for project file operations."""


def _upload_root() -> Path:
    raw = (get_settings().upload_dir or "data/uploads").strip() or "data/uploads"
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _max_bytes() -> int:
    value = int(get_settings().max_upload_bytes or DEFAULT_MAX_BYTES)
    return value if value > 0 else DEFAULT_MAX_BYTES


def safe_filename(name: str) -> str:
    base = Path(name or "file").name.replace("\x00", "")
    cleaned = re.sub(r"[^\w.\- ()\u0400-\u04FF]+", "_", base, flags=re.UNICODE)
    cleaned = cleaned.strip(" .") or "file"
    return cleaned[:180]


def extract_attachment_text(
    data: bytes,
    filename: str,
    content_type: str | None = None,
    *,
    limit: int = 8000,
) -> str:
    """Best-effort text from a customer brief (txt/md/json/csv/docx)."""
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    text = ""
    text_ext = (".txt", ".md", ".csv", ".json", ".log")
    if ctype.startswith("text/") or name.endswith(text_ext):
        text = data.decode("utf-8", errors="replace") if data else ""
    elif name.endswith(".docx") or "wordprocessingml.document" in ctype:
        try:
            import io

            from docx import Document

            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
        except Exception:
            text = ""
    compact = (text or "").strip()
    if not compact:
        return ""
    return compact[:limit]


def current_discovery_stage(db: Session, project: Project) -> str:
    kg = KnowledgeRepository(db)
    entities = kg.list_entities(project.id, type_="Project")
    if not entities:
        return DiscoveryStage.PROJECT_CREATED.value
    state = dict(entities[0].payload or {})
    return parse_stage(state.get("discovery_stage")).value


def _resolve_stage(stage: str | None, *, fallback: str) -> str:
    raw = (stage or "").strip() or fallback
    if raw == UNSCOPED_STAGE_ID:
        return UNSCOPED_STAGE_ID
    try:
        return DiscoveryStage(raw).value
    except ValueError as exc:
        raise FileError(f"unknown stage: {raw}") from exc


def _stage_label(stage: str | None) -> str:
    key = stage or ""
    if key == UNSCOPED_STAGE_ID:
        return "Вне оглавления"
    return STAGE_LABELS_RU.get(key, key or "—")


def _history_row(row, *, filename: str | None = None) -> dict[str, Any]:
    created = row.created_at
    payload = dict(row.payload or {})
    if filename and "filename" not in payload:
        payload["filename"] = filename
    return {
        "id": str(row.id),
        "entity_id": str(row.entity_id),
        "actor": row.actor,
        "action": row.action,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "reason": row.reason,
        "payload": payload,
        "created_at": created.isoformat() if isinstance(created, datetime) else created,
    }


def _serialize_file(entity: Entity) -> dict[str, Any]:
    payload = dict(entity.payload or {})
    stage = str(payload.get("stage") or "")
    rel = str(payload.get("rel_path") or "")
    stored = bool(rel) and (_upload_root() / rel).is_file()
    return {
        "id": str(entity.id),
        "filename": payload.get("filename") or entity.name,
        "content_type": payload.get("content_type") or "application/octet-stream",
        "size_bytes": int(payload.get("size_bytes") or 0),
        "stage": stage,
        "stage_label": _stage_label(stage),
        "source": payload.get("source") or "customer",
        "caption": payload.get("caption") or "",
        "downloadable": stored and entity.status != "archived",
        "legacy": False,
        "status": entity.status,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }


def _legacy_message_file(message: Message, stage: str) -> dict[str, Any]:
    meta = dict(message.meta or {})
    filename = str(meta.get("filename") or "file")
    return {
        "id": f"legacy:{message.id}",
        "filename": filename,
        "content_type": meta.get("content_type") or "application/octet-stream",
        "size_bytes": int(meta.get("size_bytes") or 0),
        "stage": stage,
        "stage_label": _stage_label(stage),
        "source": "customer",
        "caption": "",
        "downloadable": False,
        "legacy": True,
        "status": "active",
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _uploaded_artifacts(kg: KnowledgeRepository, project_id: uuid.UUID) -> list[Entity]:
    return [
        e
        for e in kg.list_entities(project_id, type_="Artifact")
        if (e.payload or {}).get("kind") == UPLOADED_KIND
    ]


def store_uploaded_file(
    db: Session,
    project: Project,
    *,
    data: bytes,
    filename: str,
    content_type: str | None = None,
    stage: str | None = None,
    source: str = "console",
    actor: str = "console",
    caption: str | None = None,
    source_message_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    blob = data or b""
    if not blob:
        raise FileError("empty file")
    if len(blob) > _max_bytes():
        raise FileError(f"file too large (max {_max_bytes()} bytes)")

    name = safe_filename(filename)
    resolved_stage = _resolve_stage(stage, fallback=current_discovery_stage(db, project))
    kg = KnowledgeRepository(db)
    entity = kg.create_entity(
        project_id=project.id,
        type_="Artifact",
        name=name,
        status="active",
        payload={
            "kind": UPLOADED_KIND,
            "filename": name,
            "content_type": (content_type or "application/octet-stream")[:180],
            "size_bytes": len(blob),
            "stage": resolved_stage,
            "source": source,
            "caption": (caption or "").strip(),
            "source_message_id": str(source_message_id) if source_message_id else None,
            "storage": "local",
        },
        confidence=1.0,
    )
    rel = Path(str(project.id)) / str(entity.id) / name
    dest = _upload_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    payload = dict(entity.payload or {})
    payload["rel_path"] = rel.as_posix()
    kg.update_entity(entity, payload=payload)
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=entity.id,
        actor=actor,
        action="created",
        to_status="active",
        payload={
            "filename": name,
            "stage": resolved_stage,
            "source": source,
            "size_bytes": len(blob),
        },
    )
    db.flush()
    return _serialize_file(entity)


def list_project_files(db: Session, project: Project) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    artifacts = _uploaded_artifacts(kg, project.id)
    covered_messages: set[str] = set()
    files: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    for entity in artifacts:
        payload = dict(entity.payload or {})
        mid = payload.get("source_message_id")
        if mid:
            covered_messages.add(str(mid))
        filename = str(payload.get("filename") or entity.name)
        history.extend(
            _history_row(row, filename=filename)
            for row in list_entity_history(db, entity.id, project_id=project.id)
        )
        if entity.status != "archived":
            files.append(_serialize_file(entity))

    current_stage = current_discovery_stage(db, project)
    messages = (
        db.query(Message)
        .filter(Message.project_id == project.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    for message in messages:
        meta = dict(message.meta or {})
        if meta.get("channel") != "file_attach":
            continue
        if str(message.id) in covered_messages:
            continue
        files.append(_legacy_message_file(message, current_stage))
        history.append(
            {
                "id": f"legacy:{message.id}",
                "entity_id": None,
                "actor": "discovery",
                "action": "created",
                "from_status": None,
                "to_status": None,
                "reason": None,
                "payload": {
                    "filename": meta.get("filename") or "file",
                    "stage": current_stage,
                    "source": "customer",
                    "legacy": True,
                },
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
        )

    files.sort(key=lambda item: item.get("created_at") or "")
    history.sort(key=lambda item: item.get("created_at") or "")
    stages = [
        {"id": stage.value, "label": STAGE_LABELS_RU.get(stage.value, stage.value)}
        for stage in DiscoveryStage
    ]
    return {
        "files": files,
        "history": history,
        "stages": stages,
        "current_stage": current_stage,
    }


def _require_file(kg: KnowledgeRepository, project_id: uuid.UUID, file_id: uuid.UUID) -> Entity:
    entity = kg.get_entity(file_id, project_id=project_id)
    if entity is None or entity.type != "Artifact":
        raise FileError("file not found")
    payload = dict(entity.payload or {})
    if payload.get("kind") != UPLOADED_KIND:
        raise FileError("file not found")
    if entity.status == "archived":
        raise FileError("file is archived")
    return entity


def read_project_file(
    db: Session, project: Project, file_id: uuid.UUID
) -> tuple[bytes, str, str]:
    kg = KnowledgeRepository(db)
    entity = _require_file(kg, project.id, file_id)
    payload = dict(entity.payload or {})
    rel = str(payload.get("rel_path") or "")
    if not rel:
        raise FileError("file content is not stored")
    path = (_upload_root() / rel).resolve()
    root = _upload_root()
    if not path.is_relative_to(root):
        raise FileError("file content is not stored")
    if not path.is_file():
        raise FileError("file content is not stored")
    filename = str(payload.get("filename") or entity.name or "file")
    content_type = str(payload.get("content_type") or "application/octet-stream")
    return path.read_bytes(), filename, content_type


def delete_project_file(
    db: Session,
    project: Project,
    file_id: uuid.UUID,
    *,
    actor: str = "console",
) -> dict[str, Any]:
    kg = KnowledgeRepository(db)
    entity = _require_file(kg, project.id, file_id)
    payload = dict(entity.payload or {})
    rel = str(payload.get("rel_path") or "")
    filename = str(payload.get("filename") or entity.name)
    if rel:
        path = _upload_root() / rel
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass
    kg.update_entity(entity, status="archived")
    record_entity_event(
        db,
        project_id=project.id,
        entity_id=entity.id,
        actor=actor,
        action="deleted",
        from_status="active",
        to_status="archived",
        payload={
            "filename": filename,
            "stage": payload.get("stage"),
            "source": payload.get("source"),
        },
    )
    db.flush()
    return list_project_files(db, project)
