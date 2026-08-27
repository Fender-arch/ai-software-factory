from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "asf-api"
    version: str = "0.1.0"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    customer_telegram_id: str | None = None
    product_type: str | None = None


class ProjectRead(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    product_type: str | None
    customer_telegram_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    text: str = Field(min_length=1)
    role: str = "customer"


class DiscoveryChoice(BaseModel):
    id: str
    label: str
    exclusive: bool = False
    recommended: bool = False


class MessageRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    role: str
    text: str
    created_at: datetime
    discovery_reply: str | None = None
    discovery_stage: str | None = None
    project_status: str | None = None
    discovery_choices: list[DiscoveryChoice] = Field(default_factory=list)
    topic_id: str | None = None
    paused: bool = False
    allow_multiple: bool = False
    tz_available: bool = False

    model_config = {"from_attributes": True}


class VoiceIngestResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    text: str
    stt_meta: dict
    discovery_reply: str | None = None
    discovery_stage: str | None = None
    project_status: str | None = None
    discovery_choices: list[DiscoveryChoice] = Field(default_factory=list)
    topic_id: str | None = None
    paused: bool = False
    allow_multiple: bool = False
    tz_available: bool = False


class HitlRequest(BaseModel):
    action: str = Field(
        description="approve | request_changes | reject",
        pattern="^(approve|request_changes|reject)$",
    )
    note: str | None = None
    actor_telegram_id: str | None = None


class HitlResponse(BaseModel):
    project_id: uuid.UUID
    action: str
    project_status: str
    artifact_id: uuid.UUID | None
    decision_id: uuid.UUID | None
    message: str
    human_decision_required: bool = False


class PlannerRequest(BaseModel):
    force: bool = False


class TaskExportResponse(BaseModel):
    project_id: uuid.UUID
    format: str
    content: str
    task_count: int
    tasks: list[dict]


class WorkspaceMessage(BaseModel):
    id: uuid.UUID
    role: str
    kind: str
    text: str
    created_at: datetime
    meta_kind: str | None = None


class DiscoveryProgress(BaseModel):
    done: int = 0
    total: int = 1
    remaining: int = 1
    ratio: float = 0.0
    percent: int = 0
    phase: str = "interview"


class WorkspaceResponse(BaseModel):
    project_id: uuid.UUID
    name: str
    status: str
    product_type: str | None
    mode: str
    discovery_stage: str | None
    it_literacy: str | None
    messages: list[WorkspaceMessage]
    discovery_choices: list[DiscoveryChoice] = Field(default_factory=list)
    topic_id: str | None = None
    paused: bool = False
    allow_multiple: bool = False
    tz_available: bool = False
    discovery_progress: DiscoveryProgress | None = None


class FeedbackRequest(BaseModel):
    text: str = Field(min_length=1)
    customer_telegram_id: str | None = None


class FeedbackResponse(BaseModel):
    project_id: uuid.UUID
    feedback_id: uuid.UUID
    message_id: uuid.UUID
    kind: str
    human_decision_required: bool
    project_status: str
    reply_to_customer: str


class TranscribeResponse(BaseModel):
    text: str
    stt_provider: str
    filename: str
