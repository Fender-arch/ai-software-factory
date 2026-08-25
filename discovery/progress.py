"""Interview progress for the Mini App status bar.

Recomputed every turn from the *current* adapted outline, so the
denominator grows when Discovery adds sections or review extras.
"""

from __future__ import annotations

from typing import Any

from core.models import Project, ProjectStatus
from discovery.closing import closing_ids
from discovery.fsm import DiscoveryStage, parse_stage
from discovery.tz_outline import plan_from_state, resolve_active_topics


def compute_discovery_progress(
    project: Project,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return done/total/ratio for the live TZ interview.

    ``total`` is not fixed: public-presence modules, capability subsections,
    clarify items, and wrap-up questions join the denominator when they
    become part of *this* interview. The bar must be redrawn from this dict
    after every answer.
    """
    payload = dict(state or {})
    plan = plan_from_state(payload)
    outline = resolve_active_topics(
        project.product_type,
        task_shape=payload.get("task_shape"),
        plan=plan,
    )
    done_ids = set(payload.get("answered_topics") or []) | set(
        payload.get("escalated_topics") or []
    )
    outline_ids = [topic.id for topic in outline]
    outline_total = max(len(outline_ids), 1)
    outline_done = sum(1 for topic_id in outline_ids if topic_id in done_ids)

    extra_total = 0
    extra_done = 0
    topic_id = str(payload.get("topic_id") or "")
    stage = parse_stage(payload.get("discovery_stage"))

    clarify_queue = [str(x) for x in (payload.get("clarify_queue") or [])]
    clarifications = [
        str(item.get("id") or "")
        for item in (payload.get("clarifications") or [])
        if isinstance(item, dict)
    ]
    clarify_done_ids = {cid for cid in clarifications if cid}
    if payload.get("clarify_initialized") or topic_id.startswith("clarify:"):
        if topic_id.startswith("clarify:"):
            clarify_queue = list(dict.fromkeys(clarify_queue + [topic_id.split(":", 1)[1]]))
        extra_total += len(set(clarify_queue) | clarify_done_ids)
        extra_done += len(clarify_done_ids)

    closing_queue = [str(x) for x in (payload.get("closing_queue") or [])]
    if payload.get("closing_initialized") or topic_id.startswith("closing:"):
        all_closing = closing_ids()
        extra_total += len(all_closing)
        remaining = set(closing_queue)
        current = str(payload.get("closing_current") or "")
        if topic_id.startswith("closing:"):
            remaining.add(topic_id.split(":", 1)[1])
        elif current:
            remaining.add(current)
        extra_done += max(0, len(all_closing) - len(remaining))

    total = max(outline_total + extra_total, 1)
    done = min(outline_done + extra_done, total)
    status = project.status
    if isinstance(status, ProjectStatus):
        status_value = status
    else:
        try:
            status_value = ProjectStatus(str(status))
        except ValueError:
            status_value = ProjectStatus.INTERVIEW

    if status_value in {
        ProjectStatus.WAITING_OWNER,
        ProjectStatus.READY,
        ProjectStatus.ARCHIVED,
    } or stage == DiscoveryStage.READY_FOR_OWNER:
        done = total
        phase = "done"
    elif extra_total and (
        topic_id.startswith("closing:") or payload.get("closing_initialized")
    ):
        phase = "closing"
    elif extra_total and (
        topic_id.startswith("clarify:") or payload.get("clarify_initialized")
    ):
        phase = "review"
    else:
        phase = "interview"

    ratio = 1.0 if total == 0 else done / total
    percent = int(round(min(max(ratio, 0.0), 1.0) * 100))
    return {
        "done": done,
        "total": total,
        "remaining": max(total - done, 0),
        "ratio": round(min(max(ratio, 0.0), 1.0), 4),
        "percent": percent,
        "phase": phase,
    }
