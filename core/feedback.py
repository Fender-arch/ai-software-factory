"""Customer implementation feedback after reviewing a delivered MVP."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from core.models import Message, MessageKind, Project, ProjectStatus
from knowledge.repository import KnowledgeRepository


class FeedbackKind(str, Enum):
    DEFECT = "defect"
    CHANGE_REQUEST = "change_request"
    NEW_REQUIREMENT = "new_requirement"


@dataclass
class FeedbackResult:
    feedback_id: uuid.UUID
    message_id: uuid.UUID
    kind: FeedbackKind
    human_decision_required: bool
    project_status: ProjectStatus
    reply_to_customer: str


_DEFECT_RE = re.compile(
    r"\b(баг|ошибк|не\s*работа|слома|crash|bug|broken|defect)\w*",
    re.IGNORECASE,
)
_CHANGE_RE = re.compile(
    r"\b(измени|поменя|вместо|передела|change\s*request|instead)\w*",
    re.IGNORECASE,
)
_NEW_RE = re.compile(
    r"\b(добав|хочу\s*ещ|новое\s*требован|add\s*feature|also\s*need)\w*",
    re.IGNORECASE,
)
_CONTRADICTION_RE = re.compile(
    r"(не\s*нужен|отмени|противореч|это\s*не\s*то|не\s*то\s*что|"
    r"cancel\s*the|not\s*what\s*we|contradict)",
    re.IGNORECASE,
)


def classify_feedback(text: str) -> FeedbackKind:
    if _DEFECT_RE.search(text):
        return FeedbackKind.DEFECT
    if _CHANGE_RE.search(text):
        return FeedbackKind.CHANGE_REQUEST
    if _NEW_RE.search(text):
        return FeedbackKind.NEW_REQUIREMENT
    return FeedbackKind.CHANGE_REQUEST


def looks_like_contradiction(text: str) -> bool:
    return bool(_CONTRADICTION_RE.search(text))


def submit_implementation_feedback(
    db: Session,
    project: Project,
    text: str,
    *,
    customer_telegram_id: str | None = None,
) -> FeedbackResult:
    if (
        customer_telegram_id
        and project.customer_telegram_id
        and str(project.customer_telegram_id) != str(customer_telegram_id)
    ):
        raise ValueError("project not owned by customer")

    kind = classify_feedback(text)
    contradiction = looks_like_contradiction(text)
    escalate = contradiction and project.status in (
        ProjectStatus.READY,
        ProjectStatus.WAITING_OWNER,
    )

    message = Message(
        project_id=project.id,
        kind=MessageKind.TEXT,
        role="customer",
        text=text,
        meta={"channel": "implementation_feedback", "feedback_kind": kind.value},
    )
    db.add(message)
    db.flush()

    kg = KnowledgeRepository(db)
    entity = kg.create_entity(
        project_id=project.id,
        type_="Feedback",
        name=text[:80] or "feedback",
        status="open" if escalate else "recorded",
        payload={
            "kind": kind.value,
            "text": text,
            "source_message_id": str(message.id),
            "contradiction_suspected": contradiction,
            "human_decision_required": escalate,
        },
    )
    projects = kg.list_entities(project.id, type_="Project")
    if projects:
        kg.create_relation(
            project_id=project.id,
            from_entity_id=entity.id,
            to_entity_id=projects[0].id,
            type_="related_to",
        )

    if escalate and project.status == ProjectStatus.READY:
        project.status = ProjectStatus.WAITING_OWNER

    if escalate:
        reply = (
            f"Замечание принято и классифицировано как {kind.value}. "
            "Требуется решение владельца "
            "(возможное противоречие с ТЗ или уточнение объёма)."
        )
    else:
        reply = (
            f"Замечание сохранено ({kind.value}). "
            "Команда учтёт его в следующих итерациях."
        )

    return FeedbackResult(
        feedback_id=entity.id,
        message_id=message.id,
        kind=kind,
        human_decision_required=escalate,
        project_status=project.status,
        reply_to_customer=reply,
    )
