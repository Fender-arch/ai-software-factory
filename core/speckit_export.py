"""Fill Spec Kit stubs from the KG + Planner export. Do not vendor spec-kit."""

from __future__ import annotations

from typing import Any

from core.models import Entity, Project
from knowledge.repository import KnowledgeRepository


def _req_line(entity: Entity) -> str:
    payload = entity.payload or {}
    text = (payload.get("description") or entity.name or "").strip()
    priority = payload.get("priority") or "should"
    return f"- `{entity.id}` [{priority}] {text}"


def render_speckit_files(
    project: Project,
    *,
    requirements: list[Entity],
    tasks: list[dict[str, Any]],
    draft_excerpt: str = "",
    escalated: list[str] | None = None,
    risks: list[str] | None = None,
) -> dict[str, str]:
    pt = project.product_type or "website"
    in_scope = "\n".join(_req_line(r) for r in requirements) or "- (none selected)"
    excerpt = (draft_excerpt or "").strip()
    if len(excerpt) > 2500:
        excerpt = excerpt[:2500] + "…"
    assumptions = escalated or []
    risk_lines = risks or []
    spec = "\n".join(
        [
            "# spec.md",
            "",
            "> Derived from the ASF Knowledge Graph / draft TZ. If this file disagrees with the KG, re-export.",
            "",
            "## Product",
            "",
            f"- Name: {project.name}",
            f"- Type: `{pt}`",
            f"- Project ID: `{project.id}`",
            "",
            "## Users",
            "",
            "- See approved draft TZ and Discovery messages.",
            "",
            "## In scope (v1)",
            "",
            in_scope,
            "",
            "## Out of scope",
            "",
            "- Anything not marked `in_mvp` / must-have on the approved slice.",
            "- Future backlog items, Redis, Neo4j, multi-agent swarm.",
            "",
            "## Primary scenario",
            "",
            excerpt or "- See draft TZ artifact.",
            "",
            "## Acceptance",
            "",
            "- Matches the in-scope requirements above.",
            "- Owner HITL leftovers stay explicit — do not guess.",
            "",
            "## Assumptions (escalated / unknown)",
            "",
            "\n".join(f"- {a}" for a in assumptions) or "- None recorded.",
            "",
            "## Risks",
            "",
            "\n".join(f"- {r}" for r in risk_lines) or "- None recorded.",
            "",
        ]
    )
    plan = "\n".join(
        [
            "# plan.md",
            "",
            "> Sufficient-simple design for the locked product type. No second architecture.",
            "",
            "## Approach",
            "",
            f"Build a simple `{pt}` MVP from the approved `in_mvp` slice. One Coordinator, one executor.",
            "",
            "## Stack",
            "",
            f"- Locked by TZ / template: `templates/{pt}.md`",
            "",
            "## DESIGN.md",
            "",
            "- Tokens and bans live in `DESIGN.md`. Do not invent a parallel look.",
            "",
            "## Interfaces",
            "",
            "- Spec Kit files + Planner task export are the Cursor brief.",
            "- Secrets arrive only via Intervention Queue (DEC-013), never from the KG.",
            "",
            "## HITL / leftovers for the owner",
            "",
            "- Telegram token, DNS, server, store passwords, Apple/Google — Intervention Queue.",
            "",
            "## Non-goals (engineering)",
            "",
            "- Redis, extra services, and multi-agent runtimes stay out unless the TZ already approved them.",
            "",
        ]
    )
    slices: list[str] = [
        "# tasks.md",
        "",
        "> Filled from ASF Planner export (`/projects/{id}/export/tasks`). Keep requirement IDs.",
        "",
        "## Slice list",
        "",
    ]
    if not tasks:
        slices.append("- (no planner tasks yet)")
    for i, task in enumerate(tasks, start=1):
        reqs = ", ".join(f"`{r}`" for r in (task.get("requirement_ids") or [])) or "—"
        criteria = task.get("acceptance_criteria") or []
        acc = "; ".join(str(c) for c in criteria) or "Done and smoke-tested"
        deps = ", ".join(task.get("depends_on") or []) or "—"
        slices.extend(
            [
                f"{i}. **[T{i}]** {task.get('title') or 'Task'}",
                f"   - Requirements: {reqs}",
                f"   - Acceptance: {acc}",
                f"   - Depends on: {deps}",
                "",
            ]
        )
    slices.extend(
        [
            "## Notes",
            "",
            "- One product type. Do not add a second app in the same slice.",
            "- Escalate blocking forks instead of guessing.",
            "",
        ]
    )
    return {"spec.md": spec, "plan.md": plan, "tasks.md": "\n".join(slices)}


def persist_cursor_brief(
    kg: KnowledgeRepository,
    project: Project,
    *,
    build_job_id: str,
    files: dict[str, str],
    requirement_ids: list[str],
    task_export_markdown: str,
) -> Entity:
    return kg.create_entity(
        project_id=project.id,
        type_="Artifact",
        name=f"Cursor brief — {project.name}",
        status="active",
        payload={
            "kind": "cursor_brief",
            "build_job_id": build_job_id,
            "files": files,
            "requirement_ids": requirement_ids,
            "task_export_markdown": task_export_markdown,
        },
    )
