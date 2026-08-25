"""Export Planner tasks for Cursor (Markdown / JSON)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from core.models import Project, Task, TaskStatus
from knowledge.repository import KnowledgeRepository

ExportFormat = Literal["markdown", "json"]


@dataclass
class TaskExport:
    project_id: uuid.UUID
    format: ExportFormat
    content: str
    task_count: int
    tasks: list[dict[str, Any]]


class ExportError(ValueError):
    """Domain error for task export."""


def list_project_tasks(db: Session, project_id: uuid.UUID) -> list[Task]:
    return list(
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.created_at.asc())
        .all()
    )


def enrich_task_dict(db: Session, project: Project, task: Task) -> dict[str, Any]:
    """Merge DB task with KG payload (requirement refs, depends_on)."""
    base = {
        "id": str(task.id),
        "project_id": str(project.id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value
        if isinstance(task.status, TaskStatus)
        else str(task.status),
        "acceptance_criteria": list(task.acceptance_criteria or []),
        "product_type": project.product_type,
        "requirement_ids": [],
        "depends_on": [],
    }
    kg = KnowledgeRepository(db)
    for ent in kg.list_entities(project.id, type_="Task"):
        payload = ent.payload or {}
        if payload.get("db_task_id") == str(task.id):
            base["requirement_ids"] = list(payload.get("requirement_ids") or [])
            base["depends_on"] = list(payload.get("depends_on") or [])
            base["entity_id"] = str(ent.id)
            break
    return base


def export_tasks(
    db: Session,
    project: Project,
    *,
    format: ExportFormat = "markdown",
) -> TaskExport:
    rows = list_project_tasks(db, project.id)
    if not rows:
        raise ExportError("no tasks to export — run Planner after HITL approval")

    tasks = [enrich_task_dict(db, project, t) for t in rows]
    if format == "json":
        content = json.dumps(
            {
                "project_id": str(project.id),
                "project_name": project.name,
                "product_type": project.product_type,
                "status": project.status.value,
                "template": f"templates/{project.product_type or 'website'}.md",
                "cursor_rules": [
                    ".cursor/rules/asf.mdc",
                    ".cursor/rules/product-templates.mdc",
                ],
                "tasks": tasks,
            },
            indent=2,
            ensure_ascii=False,
        )
    elif format == "markdown":
        content = render_tasks_markdown(project, tasks)
    else:
        raise ExportError(f"unsupported export format: {format}")

    return TaskExport(
        project_id=project.id,
        format=format,
        content=content,
        task_count=len(tasks),
        tasks=tasks,
    )


def render_tasks_markdown(project: Project, tasks: list[dict[str, Any]]) -> str:
    pt = project.product_type or "unspecified"
    lines = [
        f"# Cursor tasks — {project.name}",
        "",
        "## Meta",
        "",
        f"- Project ID: `{project.id}`",
        f"- Product type: `{pt}`",
        f"- Status: `{project.status.value}`",
        f"- Template: `templates/{pt}.md`",
        "- Rules: `.cursor/rules/asf.mdc`, `.cursor/rules/product-templates.mdc`",
        "",
        "## Instructions for Cursor",
        "",
        "1. Read the approved draft TZ and product template before coding.",
        "2. Implement tasks in order; respect `depends_on`.",
        "3. Do not invent scope beyond approved requirements.",
        "4. Raise HumanDecisionRequired instead of guessing on forks.",
        "",
        "## Tasks",
        "",
    ]
    for i, task in enumerate(tasks, start=1):
        lines.append(f"### {i}. {task['title']}")
        lines.append("")
        lines.append(f"- ID: `{task['id']}`")
        lines.append(f"- Status: `{task['status']}`")
        if task.get("requirement_ids"):
            refs = ", ".join(f"`{r}`" for r in task["requirement_ids"])
            lines.append(f"- Requirements: {refs}")
        if task.get("depends_on"):
            deps = ", ".join(task["depends_on"])
            lines.append(f"- Depends on: {deps}")
        lines.append("")
        lines.append(task.get("description") or "")
        lines.append("")
        lines.append("**Acceptance criteria**")
        lines.append("")
        criteria = task.get("acceptance_criteria") or []
        if criteria:
            for c in criteria:
                lines.append(f"- [ ] {c}")
        else:
            lines.append("- [ ] Done and smoke-tested")
        lines.append("")
    return "\n".join(lines)


def write_export_file(
    export: TaskExport,
    directory: str | Path,
    *,
    filename: str | None = None,
) -> Path:
    """Optional file write for local Cursor handoff."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    ext = "md" if export.format == "markdown" else "json"
    name = filename or f"tasks-{export.project_id}.{ext}"
    target = path / name
    target.write_text(export.content, encoding="utf-8")
    return target
