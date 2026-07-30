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


class MessageRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    role: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VoiceIngestResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    text: str
    stt_meta: dict
