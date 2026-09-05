"""Planner mode: break approved TZ into small Cursor-ready tasks (Level 0/1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from core.models import Project, ProjectStatus, Task, TaskStatus
from knowledge.repository import KnowledgeRepository
from knowledge.traceability import ensure_decision_for_requirement, link_implements


@dataclass
class PlannedTaskSpec:
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    requirement_ids: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)  # indices in plan


@dataclass
class PlannerResult:
    project_id: uuid.UUID
    task_ids: list[uuid.UUID]
    entity_ids: list[uuid.UUID]
    tasks: list[dict]
    reused_existing: bool = False


class PlannerError(ValueError):
    """Domain error for Planner."""


_BASE_CRITERIA = [
    "Matches approved draft TZ scope",
    "No Future-scope features without owner approval",
]


def plan_product_tasks(
    product_type: str | None,
    requirements: list,
) -> list[PlannedTaskSpec]:
    """Deterministic task breakdown from product type + requirements."""
    pt = product_type or "website"
    req_ids = [str(r.id) for r in requirements if r.status not in {"superseded", "archived"}]
    must_ids = [
        str(r.id)
        for r in requirements
        if r.status not in {"superseded", "archived"}
        and (r.payload or {}).get("priority", "should") == "must"
    ] or req_ids

    builders = {
        "website": _plan_website,
        "telegram_bot": _plan_telegram_bot,
        "rest_service": _plan_rest_service,
        "ai_automation": _plan_ai_automation,
        "mobile_native": _plan_mobile_native,
    }
    builder = builders.get(pt, _plan_website)
    return builder(req_ids, must_ids)


def _plan_website(req_ids: list[str], must_ids: list[str]) -> list[PlannedTaskSpec]:
    return [
        PlannedTaskSpec(
            title="Scaffold website MVP",
            description=(
                "Create a simple static or light web project structure "
                "per templates/website.md (brochure/landing)."
            ),
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Runnable locally with documented start command",
                "Product type stays website",
            ],
            requirement_ids=must_ids[:2] or req_ids[:2],
            depends_on=[],
        ),
        PlannedTaskSpec(
            title="Implement core pages and CTA",
            description=(
                "Build must-have sections/pages and primary CTA from approved requirements."
            ),
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Primary CTA visible on first viewport or home",
                "Pages match must-level requirements",
            ],
            requirement_ids=must_ids or req_ids,
            depends_on=[0],
        ),
        PlannedTaskSpec(
            title="Wire contact form destination",
            description=(
                "Implement contact/inquiry form destination from TZ "
                "(email or documented stub)."
            ),
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Form validates required fields",
                "Destination documented in README",
            ],
            requirement_ids=req_ids,
            depends_on=[1],
        ),
        PlannedTaskSpec(
            title="Responsive polish and smoke check",
            description="Ensure mobile-friendly layout; add smoke checklist to README.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Usable on narrow viewport",
                "README lists smoke steps",
            ],
            requirement_ids=must_ids[:1] or req_ids[:1],
            depends_on=[1, 2],
        ),
    ]


def _plan_mobile_native(req_ids: list[str], must_ids: list[str]) -> list[PlannedTaskSpec]:
    return [
        PlannedTaskSpec(
            title="Scaffold native mobile MVP",
            description=(
                "Create a one-platform-first project skeleton per "
                "templates/mobile_native.md (Android or iOS as locked in TZ)."
            ),
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Runnable on a simulator/emulator with a documented start command",
                "Product type stays mobile_native",
            ],
            requirement_ids=must_ids[:2] or req_ids[:2],
            depends_on=[],
        ),
        PlannedTaskSpec(
            title="Implement primary mobile job",
            description="Build the one happy-path job from approved must-level requirements.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Primary user job works on the locked platform",
            ],
            requirement_ids=must_ids or req_ids,
            depends_on=[0],
        ),
        PlannedTaskSpec(
            title="Persist minimal local state",
            description="Store enough local state for the MVP flow (documented if in-memory).",
            acceptance_criteria=[*_BASE_CRITERIA, "State survives process restart or is documented"],
            requirement_ids=req_ids,
            depends_on=[1],
        ),
        PlannedTaskSpec(
            title="Smoke build and README",
            description="Document build/run steps and a short device smoke checklist.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "README lists simulator smoke steps",
            ],
            requirement_ids=must_ids[:1] or req_ids[:1],
            depends_on=[1, 2],
        ),
    ]


def _plan_telegram_bot(req_ids: list[str], must_ids: list[str]) -> list[PlannedTaskSpec]:
    return [
        PlannedTaskSpec(
            title="Scaffold Telegram bot MVP",
            description="Bot project skeleton per templates/telegram_bot.md with /start.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Bot starts with documented token env var",
            ],
            requirement_ids=must_ids[:2] or req_ids[:2],
        ),
        PlannedTaskSpec(
            title="Implement primary user jobs",
            description="Commands or free-text flow covering must-level requirements.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Happy path for primary user job works",
            ],
            requirement_ids=must_ids or req_ids,
            depends_on=[0],
        ),
        PlannedTaskSpec(
            title="Persist minimal user state",
            description="Store enough state for the MVP flow (in-memory ok if documented).",
            acceptance_criteria=[*_BASE_CRITERIA, "State survives a multi-step dialogue"],
            requirement_ids=req_ids,
            depends_on=[1],
        ),
        PlannedTaskSpec(
            title="Smoke script and README",
            description="Document commands and a short manual smoke path.",
            acceptance_criteria=[*_BASE_CRITERIA, "README lists test commands"],
            requirement_ids=must_ids[:1] or req_ids[:1],
            depends_on=[1, 2],
        ),
    ]


def _plan_rest_service(req_ids: list[str], must_ids: list[str]) -> list[PlannedTaskSpec]:
    return [
        PlannedTaskSpec(
            title="Scaffold REST service MVP",
            description="HTTP API skeleton per templates/rest_service.md with health.",
            acceptance_criteria=[*_BASE_CRITERIA, "GET /health returns ok"],
            requirement_ids=must_ids[:2] or req_ids[:2],
        ),
        PlannedTaskSpec(
            title="Implement primary resource CRUD",
            description="One primary resource with operations from approved requirements.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Create/read path works",
                "OpenAPI or equivalent docs available",
            ],
            requirement_ids=must_ids or req_ids,
            depends_on=[0],
        ),
        PlannedTaskSpec(
            title="Add simple auth",
            description="API key or basic JWT as locked in TZ (escalate if unclear).",
            acceptance_criteria=[*_BASE_CRITERIA, "Unauthorized requests rejected"],
            requirement_ids=req_ids,
            depends_on=[1],
        ),
        PlannedTaskSpec(
            title="Tests and smoke README",
            description="pytest for happy path + auth failure; document run steps.",
            acceptance_criteria=[*_BASE_CRITERIA, "pytest covers create/read"],
            requirement_ids=must_ids[:1] or req_ids[:1],
            depends_on=[1, 2],
        ),
    ]


def _plan_ai_automation(req_ids: list[str], must_ids: list[str]) -> list[PlannedTaskSpec]:
    return [
        PlannedTaskSpec(
            title="Scaffold automation MVP",
            description="Trigger + runner skeleton per templates/ai_automation.md.",
            acceptance_criteria=[*_BASE_CRITERIA, "Documented trigger entrypoint"],
            requirement_ids=must_ids[:2] or req_ids[:2],
        ),
        PlannedTaskSpec(
            title="Implement core transform step",
            description="Rules or stub LLM step producing structured output from inputs.",
            acceptance_criteria=[*_BASE_CRITERIA, "Input→output path is testable"],
            requirement_ids=must_ids or req_ids,
            depends_on=[0],
        ),
        PlannedTaskSpec(
            title="Side effect and failure handling",
            description="Notify/write side effect; log failures without silent drop.",
            acceptance_criteria=[
                *_BASE_CRITERIA,
                "Failure path is logged",
                "HITL pause if approval required by TZ",
            ],
            requirement_ids=req_ids,
            depends_on=[1],
        ),
        PlannedTaskSpec(
            title="Run log and smoke README",
            description="Persist run summary; document how to trigger once.",
            acceptance_criteria=[*_BASE_CRITERIA, "At least one successful run logged"],
            requirement_ids=must_ids[:1] or req_ids[:1],
            depends_on=[1, 2],
        ),
    ]


def run_planner(
    db: Session,
    project: Project,
    *,
    force: bool = False,
    mvp_only: bool = False,
) -> PlannerResult:
    """Create DB tasks + KG Task entities after owner approval."""
    if project.status != ProjectStatus.READY:
        raise PlannerError(
            f"project must be READY (approved TZ and confirmed client estimate), got {project.status.value}"
        )

    existing = list(db.query(Task).filter(Task.project_id == project.id).all())
    if existing and not force:
        return PlannerResult(
            project_id=project.id,
            task_ids=[t.id for t in existing],
            entity_ids=[],
            tasks=[_task_row_dict(t) for t in existing],
            reused_existing=True,
        )

    if existing and force:
        for row in existing:
            db.delete(row)
        kg_cleanup = KnowledgeRepository(db)
        for ent in kg_cleanup.list_entities(project.id, type_="Task"):
            kg_cleanup.update_entity(ent, status="archived")
        db.flush()

    kg = KnowledgeRepository(db)
    requirements = [
        e
        for e in kg.list_entities(project.id, type_="Requirement")
        if e.status not in {"superseded", "archived"}
    ]
    if mvp_only:
        from core.mvp_slice import select_mvp_requirements

        requirements = select_mvp_requirements(requirements)
    if not requirements:
        raise PlannerError("no requirements to plan from")

    specs = plan_product_tasks(project.product_type, requirements)
    created_rows: list[Task] = []
    entity_ids: list[uuid.UUID] = []
    index_to_row: dict[int, Task] = {}

    approval = _approval_decision(kg, project.id)

    for idx, spec in enumerate(specs):
        row = Task(
            project_id=project.id,
            title=spec.title,
            description=spec.description,
            status=TaskStatus.NEW,
            acceptance_criteria=list(spec.acceptance_criteria),
        )
        db.add(row)
        db.flush()
        index_to_row[idx] = row
        created_rows.append(row)

        depends_titles = [
            index_to_row[d].title for d in spec.depends_on if d in index_to_row
        ]
        entity = kg.create_entity(
            project_id=project.id,
            type_="Task",
            name=spec.title,
            status=TaskStatus.NEW.value,
            payload={
                "title": spec.title,
                "description": spec.description,
                "acceptance_criteria": list(spec.acceptance_criteria),
                "requirement_ids": list(spec.requirement_ids),
                "depends_on": depends_titles,
                "db_task_id": str(row.id),
                "product_type": project.product_type,
            },
        )
        entity_ids.append(entity.id)

        # Trace: Requirement → Decision → Task
        linked_req = False
        for rid in spec.requirement_ids:
            try:
                req_uuid = uuid.UUID(str(rid))
            except ValueError:
                continue
            req = kg.get_entity(req_uuid, project_id=project.id)
            if req is None or req.type != "Requirement":
                continue
            decision = ensure_decision_for_requirement(kg, project.id, req)
            link_implements(kg, project.id, decision.id, entity.id)
            linked_req = True
        if not linked_req and approval is not None:
            link_implements(kg, project.id, approval.id, entity.id)

    export_artifact = kg.create_entity(
        project_id=project.id,
        type_="Artifact",
        name=f"Task backlog — {project.name}",
        status="active",
        payload={
            "kind": "task_export",
            "format": "structured",
            "task_ids": [str(t.id) for t in created_rows],
            "product_type": project.product_type,
        },
    )
    for eid in entity_ids:
        kg.create_relation(
            project_id=project.id,
            from_entity_id=eid,
            to_entity_id=export_artifact.id,
            type_="related_to",
            payload={"role": "included_in_export"},
        )

    db.flush()
    return PlannerResult(
        project_id=project.id,
        task_ids=[t.id for t in created_rows],
        entity_ids=entity_ids,
        tasks=[_task_row_dict(t) for t in created_rows],
        reused_existing=False,
    )


def _approval_decision(kg: KnowledgeRepository, project_id: uuid.UUID):
    for ent in kg.list_entities(project_id, type_="Decision"):
        if (ent.payload or {}).get("kind") == "tz_approval" and ent.status == "accepted":
            return ent
    return None


def _task_row_dict(task: Task) -> dict:
    return {
        "id": str(task.id),
        "project_id": str(task.project_id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
        "acceptance_criteria": list(task.acceptance_criteria or []),
    }
