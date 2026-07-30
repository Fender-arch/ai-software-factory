from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.api.schemas import (
    HealthResponse,
    MessageCreate,
    MessageRead,
    ProjectCreate,
    ProjectRead,
    VoiceIngestResponse,
)
from core.config import get_settings
from core.coordinator import AICoordinator, CoordinatorMode, LLMRouter
from core.db import get_db
from core.services import create_project, get_project, ingest_text_message, ingest_voice_message

settings = get_settings()
app = FastAPI(title="AI Software Factory", version="0.1.0")
coordinator = AICoordinator(LLMRouter(provider=settings.llm_provider))


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


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


@app.post("/projects/{project_id}/messages", response_model=MessageRead, status_code=201)
def api_ingest_message(
    project_id: uuid.UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
) -> MessageRead:
    try:
        message = ingest_text_message(
            db, project_id=project_id, text=body.text, role=body.role
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MessageRead.model_validate(message)


@app.post(
    "/projects/{project_id}/messages/voice",
    response_model=VoiceIngestResponse,
    status_code=201,
)
async def api_ingest_voice(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VoiceIngestResponse:
    audio = await file.read()
    try:
        message = await ingest_voice_message(
            db,
            project_id=project_id,
            audio=audio,
            filename=file.filename or "voice.ogg",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VoiceIngestResponse(
        id=message.id,
        project_id=message.project_id,
        kind=message.kind.value,
        text=message.text,
        stt_meta=message.meta or {},
    )


@app.post("/projects/{project_id}/coordinator/discovery")
async def api_run_discovery(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    result = await coordinator.run(
        CoordinatorMode.DISCOVERY,
        context={"project_id": str(project.id), "status": project.status.value},
    )
    return {
        "mode": result.mode.value,
        "provider": result.provider,
        "output": result.output,
    }
