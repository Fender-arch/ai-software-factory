"""Owner TZ graph console API (DEC-007)."""

from __future__ import annotations

from urllib.parse import quote
from typing import Literal
import secrets
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import get_settings
from core.db import get_db
from core.project_files import (
    FileError,
    delete_project_file,
    list_project_files,
    read_project_file,
    store_uploaded_file,
)
from core.requirement_console import (
    ConsoleError,
    add_requirement_relation,
    create_requirement,
    delete_requirement_relation,
    list_console_projects,
    requirement_card,
    serialize_project,
    set_requirement_status,
    update_requirement,
)
from core.tz_document import TzExportError, export_tz_file
from core.factory import FactoryError
from core.hitl import HitlError
from core.services import (
    create_project_mvp_job,
    get_project,
    get_project_mvp,
    list_project_interventions,
    resolve_project_intervention,
    send_project_mvp_to_client,
)
from knowledge.repository import KnowledgeRepository
from knowledge.tz_graph import build_tz_graph

router = APIRouter(prefix="/console/api", tags=["console"])


def _provided_console_token(
    x_console_token: str | None,
    authorization: str | None,
) -> str:
    provided = (x_console_token or "").strip()
    if provided:
        return provided
    scheme, _, rest = (authorization or "").partition(" ")
    if scheme.lower() == "bearer":
        return rest.strip()
    return ""


def require_console_auth(
    x_console_token: str | None = Header(default=None, alias="X-Console-Token"),
    authorization: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    expected = (settings.console_token or "").strip()
    if not expected:
        if settings.asf_env == "local" and settings.asf_debug:
            return
        raise HTTPException(status_code=401, detail="console token required")
    provided = _provided_console_token(x_console_token, authorization)
    if not provided or not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="invalid console token")


class RequirementStatusPatch(BaseModel):
    status: str | None = None
    reason: str | None = None
    description: str | None = None
    topic_id: str | None = None
    priority: str | None = None


class RequirementCreate(BaseModel):
    description: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    priority: str | None = None


class RequirementRelationCreate(BaseModel):
    type: Literal["depends_on", "conflicts_with"]
    peer_id: uuid.UUID


class MvpCreateRequest(BaseModel):
    force: bool = False


class InterventionResolveRequest(BaseModel):
    answer: str = Field(min_length=1)


def _project_or_404(project_id: uuid.UUID, db: Session):
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("/projects")
def console_list_projects(
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> list[dict]:
    return [serialize_project(p) for p in list_console_projects(db)]


@router.get("/projects/{project_id}/tz-graph")
def console_tz_graph(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    kg = KnowledgeRepository(db)
    return build_tz_graph(kg, project)


@router.get("/projects/{project_id}/tz-export")
def console_tz_export(
    project_id: uuid.UUID,
    format: Literal["md", "pdf", "docx"] = Query(default="md"),
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> Response:
    project = _project_or_404(project_id, db)
    try:
        payload, media, filename = export_tz_file(db, project, format)
    except TzExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ascii_name = f"tz.{format}"
    encoded = quote(filename)
    return Response(
        content=payload,
        media_type=media,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'
            )
        },
    )


@router.get("/projects/{project_id}/files")
def console_list_files(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    return list_project_files(db, project)


@router.post("/projects/{project_id}/files")
async def console_upload_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    stage: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    data = await file.read()
    try:
        stored = store_uploaded_file(
            db,
            project,
            data=data,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            stage=stage,
            source="console",
            actor="console",
        )
    except FileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    bundle = list_project_files(db, project)
    bundle["uploaded"] = stored
    return bundle


@router.get("/projects/{project_id}/files/{file_id}/content")
def console_download_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> Response:
    project = _project_or_404(project_id, db)
    try:
        payload, filename, media = read_project_file(db, project, file_id)
    except FileError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg or "archived" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    ascii_name = "file.bin"
    encoded = quote(filename)
    return Response(
        content=payload,
        media_type=media or "application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'
            )
        },
    )


@router.delete("/projects/{project_id}/files/{file_id}")
def console_delete_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    try:
        bundle = delete_project_file(db, project, file_id)
    except FileError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg or "archived" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    db.commit()
    return bundle


@router.post("/projects/{project_id}/requirements")
def console_create_requirement(
    project_id: uuid.UUID,
    body: RequirementCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    try:
        card = create_requirement(
            db,
            project,
            description=body.description,
            topic_id=body.topic_id,
            priority=body.priority,
        )
    except ConsoleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return card


@router.get("/projects/{project_id}/requirements/{requirement_id}")
def console_requirement_detail(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    try:
        return requirement_card(db, project, requirement_id)
    except ConsoleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/projects/{project_id}/requirements/{requirement_id}")
def console_requirement_status(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: RequirementStatusPatch,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    if (
        body.status is None
        and body.description is None
        and body.topic_id is None
        and body.priority is None
    ):
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        if (
            body.description is not None
            or body.topic_id is not None
            or body.priority is not None
        ):
            update_requirement(
                db,
                project,
                requirement_id,
                description=body.description,
                topic_id=body.topic_id,
                priority=body.priority,
            )
        if body.status is not None:
            card = set_requirement_status(
                db, project, requirement_id, body.status, reason=body.reason
            )
        else:
            card = requirement_card(db, project, requirement_id)
    except ConsoleError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg or "archived" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    db.commit()
    return card


@router.post("/projects/{project_id}/requirements/{requirement_id}/relations")
def console_add_relation(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: RequirementRelationCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    try:
        card = add_requirement_relation(
            db,
            project,
            requirement_id,
            rel_type=body.type,
            peer_id=body.peer_id,
        )
    except ConsoleError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg or "archived" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    db.commit()
    return card


@router.delete("/projects/{project_id}/relations/{relation_id}")
def console_delete_relation(
    project_id: uuid.UUID,
    relation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    project = _project_or_404(project_id, db)
    try:
        card = delete_requirement_relation(db, project, relation_id)
    except ConsoleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return card


@router.get("/projects/{project_id}/mvp")
def console_get_mvp(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    _project_or_404(project_id, db)
    try:
        return get_project_mvp(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/mvp")
def console_create_mvp(
    project_id: uuid.UUID,
    body: MvpCreateRequest | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    _project_or_404(project_id, db)
    force = body.force if body else False
    try:
        return create_project_mvp_job(db, project_id, force=force)
    except FactoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HitlError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/mvp/send-to-client")
def console_send_mvp(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    _project_or_404(project_id, db)
    try:
        return send_project_mvp_to_client(db, project_id)
    except FactoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HitlError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/interventions")
def console_list_interventions(
    project_id: uuid.UUID,
    status: str | None = Query(default="open"),
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    _project_or_404(project_id, db)
    try:
        items = list_project_interventions(db, project_id, status=status or None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"interventions": items}


@router.post("/interventions/{intervention_id}/resolve")
def console_resolve_intervention(
    intervention_id: uuid.UUID,
    body: InterventionResolveRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_console_auth),
) -> dict:
    try:
        return resolve_project_intervention(db, intervention_id, body.answer)
    except FactoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HitlError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
