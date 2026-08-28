from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from core.models import Entity, Project
from discovery.tz_outline import OutlinePlan, remaining_topics, resolve_active_topics

logger = logging.getLogger(__name__)

_POLISH_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "tz-polish.md"

_FR_TOPICS = (
    "must_features",
    "pages_sections",
    "delivery_surface",
    "interaction_model",
    "public_identity",
    "offer_catalog",
    "visitor_cta",
    "resources_ops",
    "trigger_io",
    "admin_operations",
    "booking_rules",
    "notification_rules",
    "voice_input",
    "api_consumers",
)
_SC_TOPICS = ("success_mvp", "acceptance")
_EXTRA_TZ_SECTIONS = (
    ("closing_additions", "Customer additions"),
    ("source_brief", "Source brief (file / LLM chat)"),
)


def render_draft_tz(
    project: Project,
    *,
    requirements: list[Entity],
    open_questions: list[Entity],
    risks: list[Entity] | None = None,
    literacy: str | None = None,
    discovery_stage: str | None = None,
    answered_topics: list[str] | None = None,
    escalated_topics: list[str] | None = None,
    task_shape: str | None = None,
    assumptions: list[str] | None = None,
    clarifications: list[dict] | None = None,
    plan: OutlinePlan | None = None,
) -> str:
    """Markdown draft TZ derived from KG entities (not a competing store)."""
    risks = risks or []
    answered = set(answered_topics or [])
    escalated = set(escalated_topics or [])
    done = answered | escalated
    outline = resolve_active_topics(project.product_type, task_shape=task_shape, plan=plan)
    leftover = remaining_topics(
        project.product_type, task_shape=task_shape, done_ids=done, plan=plan
    )

    req_by_topic: dict[str, list[Entity]] = {}
    unscoped: list[Entity] = []
    supplements: list[Entity] = []
    for ent in requirements:
        if ent.status == "superseded":
            continue
        tid = str((ent.payload or {}).get("topic_id") or "")
        if tid == "owner_review_supplement":
            supplements.append(ent)
        elif tid:
            req_by_topic.setdefault(tid, []).append(ent)
        else:
            unscoped.append(ent)

    lines = [
        f"# Draft TZ — {project.name}",
        "",
        "## Meta",
        "",
        f"- Project ID: `{project.id}`",
        f"- Product type: `{project.product_type or 'unspecified'}`",
        f"- Task shape: `{task_shape or 'unspecified'}`",
        f"- Status: `{project.status.value}`",
        f"- Discovery stage: `{discovery_stage or 'READY_FOR_OWNER'}`",
        f"- Customer IT literacy (heuristic): `{literacy or 'low'}`",
        f"- TZ sections covered: `{len(done)}/{max(len(outline), 1)}`",
        f"- Outline capabilities: `{', '.join(sorted(plan.capabilities)) if plan and plan.capabilities else 'default catalog'}`",
        "",
        "## Vision / problem",
        "",
    ]

    vision = _first_for_topic(req_by_topic, "purpose_problem") or _first_payload(
        requirements, "stage", "UNDERSTANDING_IDEA"
    )
    if vision:
        lines.append(vision)
    else:
        lines.append("_No vision statement captured yet._")

    scenario = _first_for_topic(req_by_topic, "primary_scenario")
    acceptance = _first_for_topic(req_by_topic, "acceptance")
    lines.extend(["", "## User stories", ""])
    if scenario or acceptance:
        lines.append("### User Story 1 - Primary journey (Priority: P1)")
        lines.append("")
        lines.append(scenario or "_Primary scenario not captured._")
        lines.append("")
        lines.append(
            "**Independent Test**: Customer can complete the primary path on real data."
        )
        lines.append("")
        lines.append("**Acceptance Scenarios**:")
        lines.append("")
        given = _first_for_topic(req_by_topic, "as_is_process") or "the MVP is deployed"
        when = scenario or "the user follows the primary path"
        then = acceptance or "the customer accepts the result"
        lines.append(
            f"1. **Given** {given}, **When** {when}, **Then** {then}."
        )
    else:
        lines.append("_No primary scenario captured yet._")

    lines.extend(["", "## TZ sections", ""])
    if not outline:
        lines.append("_No outline available._")
    else:
        for topic in outline:
            status = (
                "escalated to developer"
                if topic.id in escalated
                else "captured"
                if topic.id in answered
                else "missing"
            )
            lines.append(f"### {topic.title_en} (`{topic.id}`, {status})")
            lines.append("")
            ents = req_by_topic.get(topic.id) or []
            if ents:
                for ent in ents:
                    desc = (ent.payload or {}).get("description") or ent.name
                    priority = (ent.payload or {}).get("priority", "should")
                    lines.append(f"- **[{priority}]** {desc}")
            elif topic.id in escalated:
                lines.append("- _Handed to developer / owner as an open question._")
            else:
                lines.append("- _Not captured._")
            lines.append("")

    for extra_id, extra_title in _EXTRA_TZ_SECTIONS:
        ents = req_by_topic.get(extra_id) or []
        if not ents:
            continue
        lines.append(f"### {extra_title} (`{extra_id}`, captured)")
        lines.append("")
        for ent in ents:
            desc = (ent.payload or {}).get("description") or ent.name
            priority = (ent.payload or {}).get("priority", "should")
            lines.append(f"- **[{priority}]** {desc}")
        lines.append("")

    lines.extend(["", "## Functional requirements", ""])
    fr_ents: list[Entity] = []
    for tid in _FR_TOPICS:
        fr_ents.extend(req_by_topic.get(tid) or [])
    if not fr_ents:
        lines.append("_No must-have functions captured yet._")
    else:
        for idx, ent in enumerate(fr_ents, start=1):
            desc = (ent.payload or {}).get("description") or ent.name
            lines.append(f"- **FR-{idx:03d}**: {desc}")

    lines.extend(["", "## Success criteria", ""])
    sc_ents: list[Entity] = []
    for tid in _SC_TOPICS:
        sc_ents.extend(req_by_topic.get(tid) or [])
    if not sc_ents:
        lines.append("_No measurable success criteria captured yet._")
    else:
        for idx, ent in enumerate(sc_ents, start=1):
            desc = (ent.payload or {}).get("description") or ent.name
            lines.append(f"- **SC-{idx:03d}**: {desc}")

    assumption_lines = [str(a).strip() for a in (assumptions or []) if str(a).strip()]
    lines.extend(["", "## Assumptions", ""])
    if assumption_lines:
        for line in assumption_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- Simple MVP delivery unless a captured constraint says otherwise.")
        lines.append("- Commercial timeline and budget are constraints for the owner, not a substitute for HITL.")

    clarif_lines = [c for c in (clarifications or []) if isinstance(c, dict)]
    lines.extend(["", "## Clarifications", ""])
    if not clarif_lines:
        lines.append("_No dedicated clarify-pass answers._")
    else:
        for row in clarif_lines:
            q = str(row.get("q") or row.get("id") or "Clarification")
            a = str(row.get("a") or "")
            lines.append(f"- Q: {q} → A: {a}")

    if supplements:
        lines.extend(["## Customer supplements after review", ""])
        for ent in supplements:
            desc = (ent.payload or {}).get("description") or ent.name
            lines.append(f"- {desc}")
        lines.append("")

    if unscoped:
        lines.extend(["## Other requirements", ""])
        for ent in unscoped:
            if ent.status == "superseded":
                continue
            priority = (ent.payload or {}).get("priority", "should")
            desc = (ent.payload or {}).get("description") or ent.name
            lines.append(f"- **[{priority}] {ent.name}**: {desc}")
        lines.append("")

    lines.extend(["", "## Open questions", ""])
    open_active = [e for e in open_questions if e.status == "open"]
    if not open_active:
        lines.append("_None._")
    else:
        for ent in open_active:
            q = (ent.payload or {}).get("question") or ent.name
            lines.append(f"- {q}")

    lines.extend(["", "## Risks", ""])
    if not risks:
        lines.append("_None recorded._")
    else:
        for ent in risks:
            desc = (ent.payload or {}).get("description") or ent.name
            lines.append(f"- {desc}")

    lines.extend(
        [
            "",
            "## Draft MVP scope",
            "",
            f"Deliver a simple `{project.product_type or 'product'}` MVP aligned with "
            "the must-level requirements above. Over-scoped items escalate to owner.",
            "",
            "## Uncovered sections",
            "",
        ]
    )
    if leftover:
        for topic in leftover:
            lines.append(f"- {topic.title_en} (`{topic.id}`)")
    else:
        lines.append("_All applicable TZ sections captured or escalated._")

    lines.extend(
        [
            "",
            "## Recommendations for owner review",
            "",
            "- Approve, request changes, or answer open questions before planning.",
            "- Follow up via the preferred contact channel; treat budget and timeline as commercial constraints, not a substitute for owner HITL.",
            "- Development planning starts only after owner approval (HITL).",
            "- Items marked `escalated to developer` need a human decision, not a guess.",
            "",
        ]
    )
    return "\n".join(lines)


def _first_for_topic(req_by_topic: dict[str, list[Entity]], topic_id: str) -> str | None:
    ents = req_by_topic.get(topic_id) or []
    if not ents:
        return None
    return str((ents[0].payload or {}).get("description") or ents[0].name)


def _first_payload(entities: list[Entity], key: str, value: str) -> str | None:
    for ent in entities:
        payload = ent.payload or {}
        if payload.get(key) == value:
            return str(payload.get("description") or ent.name)
    if entities:
        return str((entities[0].payload or {}).get("description") or entities[0].name)
    return None


def _load_polish_prompt() -> str:
    try:
        return _POLISH_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "Rewrite the draft TZ as one coherent Russian Markdown document. "
            "Keep every fact, FR-/SC- id and [NEEDS CLARIFICATION] marker. "
            'JSON only: {"polished_markdown": "..."}'
        )


def polish_draft_tz(
    markdown: str,
    llm_json: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> str | None:
    """Optional LLM narrative pass over the rendered draft TZ.

    Returns the polished markdown, or None when the polish is unavailable or
    fails the guards (caller keeps the raw draft).
    """
    if not markdown or len(markdown) < 400:
        return None
    if llm_json is None:
        from integrations.llm import complete_json

        llm_json = complete_json
    try:
        raw = llm_json(
            _load_polish_prompt(),
            json.dumps({"draft_markdown": markdown}, ensure_ascii=False),
        )
    except Exception:
        logger.exception("TZ polish call failed; keeping raw draft")
        return None
    if not isinstance(raw, dict):
        return None
    polished = str(raw.get("polished_markdown") or "").strip()
    if not polished:
        return None
    ratio = len(polished) / max(len(markdown), 1)
    if not 0.4 <= ratio <= 2.5:
        return None
    for marker in ("FR-", "SC-", "[NEEDS CLARIFICATION]"):
        if markdown.count(marker) and polished.count(marker) < markdown.count(marker):
            return None
    return polished
