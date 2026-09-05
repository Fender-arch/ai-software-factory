"""Compose and export the full TZ document from the knowledge graph."""

from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from core.models import Project
from discovery.artifacts import render_draft_tz
from discovery.fsm import DiscoveryStage
from discovery.tz_outline import plan_from_state, resolve_active_topics
from knowledge.repository import KnowledgeRepository
from knowledge.types import normalize_requirement_status
from knowledge.tz_graph import STAGE_LABELS_RU

TzExportFormat = Literal["md", "pdf", "docx"]

STATUS_RU = {
    "new": "новое",
    "processed": "отработано",
    "needs_clarification": "уточняется",
    "conflict": "конфликт",
    "rejected": "отклонено",
    "superseded": "заменено",
}

PRODUCT_RU = {
    "website": "сайт",
    "telegram_bot": "Telegram-бот",
    "rest_service": "REST-сервис",
    "ai_automation": "AI-автоматизация",
    "mobile_native": "нативное приложение",
}

_FONT_CANDIDATES = (
    Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf",
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
)


class TzExportError(ValueError):
    """Could not build a TZ file."""


def _project_state(kg: KnowledgeRepository, project: Project) -> dict:
    entities = kg.list_entities(project.id, type_="Project")
    if not entities:
        return {}
    return dict(entities[0].payload or {})


def compose_tz_markdown(db: Session, project: Project) -> str:
    """Full TZ in Russian, derived from current KG (not a competing store)."""
    kg = KnowledgeRepository(db)
    state = _project_state(kg, project)
    requirements = [
        e
        for e in kg.list_entities(project.id, type_="Requirement")
        if e.status != "archived"
    ]
    open_questions = kg.list_entities(project.id, type_="OpenQuestion")
    risks = kg.list_entities(project.id, type_="Risk")
    task_shape = state.get("task_shape")
    plan = plan_from_state(state)
    outline = resolve_active_topics(project.product_type, task_shape=task_shape, plan=plan)

    req_by_topic: dict[str, list] = {}
    unscoped: list = []
    for ent in requirements:
        if normalize_requirement_status(ent.status) == "superseded":
            continue
        tid = str((ent.payload or {}).get("topic_id") or "")
        if tid:
            req_by_topic.setdefault(tid, []).append(ent)
        else:
            unscoped.append(ent)

    product = PRODUCT_RU.get(project.product_type or "", project.product_type or "не задан")
    lines = [
        f"# Техническое задание — {project.name}",
        "",
        "## Мета",
        "",
        f"- Идентификатор: `{project.id}`",
        f"- Тип продукта: {product} (`{project.product_type or 'unspecified'}`)",
        f"- Форма задачи: `{task_shape or '—'}`",
        f"- Статус проекта: `{project.status.value}`",
        f"- Этап Discovery: `{state.get('stage') or '—'}`",
        "",
    ]

    current_stage = None
    for topic in outline:
        stage_key = topic.stage.value
        if stage_key != current_stage:
            current_stage = stage_key
            label = STAGE_LABELS_RU.get(stage_key, stage_key)
            lines.extend([f"## {label}", ""])
        lines.append(f"### {topic.title_ru}")
        lines.append("")
        ents = req_by_topic.get(topic.id) or []
        if not ents:
            lines.append("_Пока не зафиксировано._")
            lines.append("")
            continue
        for ent in ents:
            payload = ent.payload or {}
            desc = payload.get("description") or ent.name
            status = STATUS_RU.get(
                normalize_requirement_status(ent.status), ent.status or ""
            )
            priority = payload.get("priority") or "should"
            lines.append(f"- **[{status}]** ({priority}) {desc}")
        lines.append("")

    extra_ru = (
        ("closing_additions", "Дополнения заказчика"),
        ("source_brief", "Исходная постановка (файл / нейросеть)"),
    )
    extra_ids = {tid for tid, _ in extra_ru}
    for extra_id, extra_title in extra_ru:
        ents = req_by_topic.get(extra_id) or []
        if not ents:
            continue
        lines.extend([f"## {extra_title}", ""])
        for ent in ents:
            payload = ent.payload or {}
            desc = payload.get("description") or ent.name
            status = STATUS_RU.get(
                normalize_requirement_status(ent.status), ent.status or ""
            )
            priority = payload.get("priority") or "should"
            lines.append(f"- **[{status}]** ({priority}) {desc}")
        lines.append("")

    unscoped = [e for e in unscoped if str((e.payload or {}).get("topic_id") or "") not in extra_ids]

    if unscoped:
        lines.extend(["## Прочие требования", ""])
        for ent in unscoped:
            payload = ent.payload or {}
            desc = payload.get("description") or ent.name
            status = STATUS_RU.get(
                normalize_requirement_status(ent.status), ent.status or ""
            )
            lines.append(f"- **[{status}]** {desc}")
        lines.append("")

    lines.extend(["## Открытые вопросы", ""])
    open_active = [e for e in open_questions if e.status == "open"]
    if not open_active:
        lines.append("_Нет._")
    else:
        for ent in open_active:
            q = (ent.payload or {}).get("question") or ent.name
            lines.append(f"- {q}")
    lines.append("")

    lines.extend(["## Риски", ""])
    if not risks:
        lines.append("_Не записаны._")
    else:
        for ent in risks:
            desc = (ent.payload or {}).get("description") or ent.name
            lines.append(f"- {desc}")
    lines.append("")

    # Keep a machine-readable English draft appendix for Cursor/HITL compatibility.
    appendix = render_draft_tz(
        project,
        requirements=requirements,
        open_questions=open_questions,
        risks=risks,
        literacy=str(state.get("it_literacy") or "low"),
        discovery_stage=str(state.get("stage") or DiscoveryStage.READY_FOR_OWNER.value),
        answered_topics=list(state.get("answered_topics") or []),
        escalated_topics=list(state.get("escalated_topics") or []),
        task_shape=task_shape,
        plan=plan,
    )
    lines.extend(["---", "", "## Appendix: draft TZ (EN)", "", appendix, ""])
    return "\n".join(lines)


def _safe_stem(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", (name or "tz").strip(), flags=re.UNICODE)
    return (slug.strip("-") or "tz")[:72]


def _cyrillic_font() -> Path:
    for path in _FONT_CANDIDATES:
        if path.is_file():
            return path
    raise TzExportError("no Unicode TTF found for PDF export")


def markdown_to_docx(markdown: str) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("- "):
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        elif line == "---":
            doc.add_paragraph("—" * 12)
        else:
            doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def markdown_to_pdf(markdown: str) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    font = _cyrillic_font()
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.add_font("TzSans", fname=str(font))
    pdf.set_text_color(28, 32, 38)
    usable = pdf.epw

    def write(text: str, size: int, height: float) -> None:
        pdf.set_font("TzSans", size=size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            usable,
            height,
            text,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    for raw in markdown.splitlines():
        line = raw.replace("\t", "  ")
        if not line.strip():
            pdf.ln(3)
            continue
        if line.startswith("# "):
            write(line[2:].strip(), 18, 9)
            pdf.ln(2)
        elif line.startswith("## "):
            write(line[3:].strip(), 14, 8)
            pdf.ln(1)
        elif line.startswith("### "):
            write(line[4:].strip(), 12, 7)
        elif line.startswith("- "):
            write(f"- {line[2:].strip()}", 11, 6)
        else:
            write(line, 11, 6)
    return bytes(pdf.output())


def export_tz_file(
    db: Session, project: Project, fmt: TzExportFormat
) -> tuple[bytes, str, str]:
    markdown = compose_tz_markdown(db, project)
    stem = _safe_stem(project.name)
    if fmt == "md":
        return markdown.encode("utf-8"), "text/markdown; charset=utf-8", f"{stem}.md"
    if fmt == "docx":
        return (
            markdown_to_docx(markdown),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"{stem}.docx",
        )
    if fmt == "pdf":
        return markdown_to_pdf(markdown), "application/pdf", f"{stem}.pdf"
    raise TzExportError(f"unsupported format: {fmt}")


def export_tz_for_project(
    db: Session, project_id: uuid.UUID, fmt: TzExportFormat
) -> tuple[bytes, str, str]:
    from core.services import get_project

    project = get_project(db, project_id)
    if project is None:
        raise TzExportError("project not found")
    return export_tz_file(db, project, fmt)
