from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.console import router as console_router
from apps.api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    HitlRequest,
    HitlResponse,
    MessageCreate,
    MessageRead,
    PlannerRequest,
    ProjectCreate,
    ProjectRead,
    TaskExportResponse,
    TranscribeResponse,
    VoiceIngestResponse,
    WorkspaceMessage,
    WorkspaceResponse,
)
from integrations.stt import get_stt_provider
from core.config import get_settings
from core.coordinator import AICoordinator, LLMRouter
from core.db import get_db
from core.export import ExportError
from core.hitl import HitlError
from core.planner import PlannerError
from core.models import ProjectStatus
from core.project_files import FileError
from core.tz_document import TzExportError, export_tz_file
from core.services import (
    assert_project_owner,
    create_project,
    delete_project,
    export_project_tasks,
    get_owner_review,
    get_project,
    get_project_workspace,
    ingest_file_message,
    ingest_text_message,
    ingest_voice_message,
    list_projects_for_customer,
    run_project_discovery,
    run_project_planner,
    submit_hitl_decision,
    submit_project_feedback,
)
from knowledge.repository import KnowledgeRepository

settings = get_settings()
app = FastAPI(title="AI Software Factory", version="0.1.0")
app.include_router(console_router)
coordinator = AICoordinator(LLMRouter(provider=settings.llm_provider))

_MINIAPP_DIR = Path(__file__).resolve().parents[1] / "miniapp"
_CONSOLE_DIR = Path(__file__).resolve().parents[1] / "console"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/stt/transcribe", response_model=TranscribeResponse)
async def api_transcribe(file: UploadFile = File(...)) -> TranscribeResponse:
    """Speech-to-text only — does not create project messages (Mini App dictation)."""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="empty audio")
    filename = file.filename or "voice.webm"
    stt = get_stt_provider()
    try:
        text = await stt.transcribe(audio, filename=filename)
    except Exception as exc:  # noqa: BLE001 — surface provider errors to Mini App
        msg = str(exc)
        low = msg.lower()
        if "429" in msg or "insufficient_quota" in low or "quota" in low:
            detail = (
                "Распознавание недоступно: квота облачного STT исчерпана. "
                "Проверьте GROQ_API_KEY / OpenAI billing или используйте Web Speech в Mini App."
            )
        elif "groq_api_key" in low or "groq api key" in low:
            detail = (
                "Не задан GROQ_API_KEY. Добавьте ключ в .env и выставьте STT_PROVIDER=groq."
            )
        else:
            detail = f"Не удалось распознать речь: {msg}"
        raise HTTPException(status_code=502, detail=detail) from exc
    return TranscribeResponse(
        text=(text or "").strip(),
        stt_provider=stt.__class__.__name__,
        filename=filename,
    )


@app.get("/projects", response_model=list[ProjectRead])
def api_list_projects(
    customer_telegram_id: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> list[ProjectRead]:
    projects = list_projects_for_customer(db, customer_telegram_id)
    return [ProjectRead.model_validate(p) for p in projects]


@app.post("/projects", response_model=ProjectRead, status_code=201)
def api_create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    project = create_project(
        db,
        name=body.name,
        customer_telegram_id=body.customer_telegram_id,
        product_type=body.product_type,
    )
    return ProjectRead.model_validate(project)


@app.get("/projects/{project_id}", response_model=ProjectRead)
def api_get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ProjectRead:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectRead.model_validate(project)


@app.delete("/projects/{project_id}", status_code=204)
def api_delete_project(
    project_id: uuid.UUID,
    customer_telegram_id: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_project(db, project_id, customer_telegram_id=customer_telegram_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/projects/{project_id}/workspace", response_model=WorkspaceResponse)
def api_project_workspace(
    project_id: uuid.UUID,
    customer_telegram_id: str | None = None,
    mode: str = Query(default="create"),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    try:
        ws = get_project_workspace(
            db,
            project_id,
            customer_telegram_id=customer_telegram_id,
            mode=mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    project = ws["project"]
    return WorkspaceResponse(
        project_id=project.id,
        name=project.name,
        status=project.status.value,
        product_type=project.product_type,
        mode=ws["mode"],
        discovery_stage=ws["discovery_stage"],
        it_literacy=ws["it_literacy"],
        messages=[
            WorkspaceMessage(
                id=m.id,
                role=m.role,
                kind=m.kind.value,
                text=m.text,
                created_at=m.created_at,
            )
            for m in ws["messages"]
        ],
        discovery_choices=ws.get("discovery_choices") or [],
        topic_id=ws.get("topic_id"),
        paused=bool(ws.get("paused")),
        allow_multiple=bool(ws.get("allow_multiple")),
        tz_available=bool(ws.get("tz_available")),
        discovery_progress=ws.get("discovery_progress"),
    )


@app.post("/projects/{project_id}/messages", response_model=MessageRead, status_code=201)
def api_ingest_message(
    project_id: uuid.UUID,
    body: MessageCreate,
    customer_telegram_id: str | None = None,
    db: Session = Depends(get_db),
) -> MessageRead:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        assert_project_owner(project, customer_telegram_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        result = ingest_text_message(
            db, project_id=project_id, text=body.text, role=body.role
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить ответ. Если это повторяется — примените миграции БД (alembic upgrade head).",
        ) from exc

    message = result.message
    discovery = result.discovery
    return MessageRead(
        id=message.id,
        project_id=message.project_id,
        kind=message.kind.value,
        role=message.role,
        text=message.text,
        created_at=message.created_at,
        discovery_reply=discovery.reply_to_customer if discovery else None,
        discovery_stage=discovery.stage.value if discovery else None,
        project_status=discovery.project_status.value if discovery else None,
        discovery_choices=discovery.choices if discovery else [],
        topic_id=discovery.topic_id if discovery else None,
        paused=discovery.paused if discovery else False,
        allow_multiple=discovery.allow_multiple if discovery else False,
        tz_available=discovery.tz_available if discovery else False,
    )


@app.post(
    "/projects/{project_id}/messages/voice",
    response_model=VoiceIngestResponse,
    status_code=201,
)
async def api_ingest_voice(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    customer_telegram_id: str | None = None,
    run_discovery: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> VoiceIngestResponse:
    audio = await file.read()
    try:
        result = await ingest_voice_message(
            db,
            project_id=project_id,
            audio=audio,
            filename=file.filename or "voice.ogg",
            customer_telegram_id=customer_telegram_id,
            run_discovery=run_discovery,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    message = result.message
    discovery = result.discovery
    return VoiceIngestResponse(
        id=message.id,
        project_id=message.project_id,
        kind=message.kind.value,
        text=message.text,
        stt_meta=message.meta or {},
        discovery_reply=discovery.reply_to_customer if discovery else None,
        discovery_stage=discovery.stage.value if discovery else None,
        project_status=discovery.project_status.value if discovery else None,
        discovery_choices=discovery.choices if discovery else [],
        topic_id=discovery.topic_id if discovery else None,
        paused=discovery.paused if discovery else False,
        allow_multiple=discovery.allow_multiple if discovery else False,
        tz_available=discovery.tz_available if discovery else False,
    )


@app.post(
    "/projects/{project_id}/messages/file",
    response_model=VoiceIngestResponse,
    status_code=201,
)
async def api_ingest_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    caption: str | None = None,
    customer_telegram_id: str | None = None,
    db: Session = Depends(get_db),
) -> VoiceIngestResponse:
    data = await file.read()
    try:
        result = await ingest_file_message(
            db,
            project_id,
            data=data,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            caption=caption,
            customer_telegram_id=customer_telegram_id,
        )
    except FileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    message = result.message
    discovery = result.discovery
    return VoiceIngestResponse(
        id=message.id,
        project_id=message.project_id,
        kind=message.kind.value,
        text=message.text,
        stt_meta=message.meta or {},
        discovery_reply=discovery.reply_to_customer if discovery else None,
        discovery_stage=discovery.stage.value if discovery else None,
        project_status=discovery.project_status.value if discovery else None,
        discovery_choices=discovery.choices if discovery else [],
        topic_id=discovery.topic_id if discovery else None,
        paused=discovery.paused if discovery else False,
        allow_multiple=discovery.allow_multiple if discovery else False,
        tz_available=discovery.tz_available if discovery else False,
    )


@app.post(
    "/projects/{project_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
def api_project_feedback(
    project_id: uuid.UUID,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    try:
        result = submit_project_feedback(
            db,
            project_id,
            body.text,
            customer_telegram_id=body.customer_telegram_id,
        )
    except ValueError as exc:
        if str(exc) == "project not found":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FeedbackResponse(
        project_id=project_id,
        feedback_id=result.feedback_id,
        message_id=result.message_id,
        kind=result.kind.value,
        human_decision_required=result.human_decision_required,
        project_status=result.project_status.value,
        reply_to_customer=result.reply_to_customer,
    )


@app.post("/projects/{project_id}/coordinator/discovery")
async def api_run_discovery(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return await run_project_discovery(db, project_id, coordinator=coordinator)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/artifacts/draft-tz")
def api_get_draft_tz(project_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    kg = KnowledgeRepository(db)
    artifacts = [
        e
        for e in kg.list_entities(project.id, type_="Artifact")
        if (e.payload or {}).get("kind") == "draft_tz"
    ]
    if not artifacts:
        raise HTTPException(status_code=404, detail="draft TZ not found")
    latest = artifacts[-1]
    return {
        "id": str(latest.id),
        "name": latest.name,
        "status": latest.status,
        "content": (latest.payload or {}).get("content", ""),
    }


@app.get("/projects/{project_id}/tz-export")
def api_customer_tz_export(
    project_id: uuid.UUID,
    format: Literal["md", "pdf", "docx"] = Query(default="md"),
    customer_telegram_id: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        assert_project_owner(project, customer_telegram_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if project.status not in {
        ProjectStatus.WAITING_OWNER,
        ProjectStatus.READY,
        ProjectStatus.ARCHIVED,
    }:
        raise HTTPException(status_code=409, detail="draft TZ is not ready yet")
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


@app.get("/projects/{project_id}/hitl/review")
def api_hitl_review(project_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return get_owner_review(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/hitl", response_model=HitlResponse)
def api_hitl_decision(
    project_id: uuid.UUID,
    body: HitlRequest,
    db: Session = Depends(get_db),
) -> HitlResponse:
    try:
        result = submit_hitl_decision(
            db,
            project_id,
            body.action,
            note=body.note,
            actor_telegram_id=body.actor_telegram_id,
        )
    except ValueError as exc:
        if str(exc) == "project not found":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HitlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return HitlResponse(
        project_id=result.project_id,
        action=result.action.value,
        project_status=result.project_status.value,
        artifact_id=result.artifact_id,
        decision_id=result.decision_id,
        message=result.message,
        human_decision_required=result.human_decision_required,
    )


@app.post("/projects/{project_id}/coordinator/planner")
async def api_run_planner(
    project_id: uuid.UUID,
    body: PlannerRequest | None = None,
    db: Session = Depends(get_db),
) -> dict:
    force = body.force if body else False
    try:
        return await run_project_planner(
            db, project_id, coordinator=coordinator, force=force
        )
    except ValueError as exc:
        if str(exc) == "project not found":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PlannerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/{project_id}/export/tasks", response_model=TaskExportResponse)
def api_export_tasks(
    project_id: uuid.UUID,
    format: Literal["markdown", "json"] = Query(default="markdown"),
    db: Session = Depends(get_db),
) -> TaskExportResponse:
    try:
        exported = export_project_tasks(db, project_id, format=format)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TaskExportResponse(
        project_id=exported.project_id,
        format=exported.format,
        content=exported.content,
        task_count=exported.task_count,
        tasks=exported.tasks,
    )


if _MINIAPP_DIR.is_dir():
    app.mount(
        "/miniapp",
        StaticFiles(directory=str(_MINIAPP_DIR), html=True),
        name="miniapp",
    )

if _CONSOLE_DIR.is_dir():
    app.mount(
        "/console",
        StaticFiles(directory=str(_CONSOLE_DIR), html=True),
        name="console",
    )
