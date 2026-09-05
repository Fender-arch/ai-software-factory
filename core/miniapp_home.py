"""Mini App home (project hub) actions from customer project state."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models import BuildJob, BuildJobStatus

HOME_ACTION_CREATE = "create"
HOME_ACTION_CHANGE = "change"
HOME_ACTION_FEEDBACK = "feedback"

HOME_ACTIONS_EMPTY = (HOME_ACTION_CREATE,)
HOME_ACTIONS_WITH_PROJECT = (HOME_ACTION_CREATE, HOME_ACTION_CHANGE)
HOME_ACTIONS_WITH_MVP_REVIEW = (
    HOME_ACTION_CREATE,
    HOME_ACTION_CHANGE,
    HOME_ACTION_FEEDBACK,
)


def home_actions(*, project_count: int, has_mvp_review: bool) -> list[str]:
    """Which home buttons to show.

    0 projects → create only.
    Has a project, but MVP was never sent for client review → create + change.
    At least one project already sent to the client (``sent_to_client``) →
    also implementation feedback. READY without a sent build does not count.
    """
    if int(project_count or 0) <= 0:
        return list(HOME_ACTIONS_EMPTY)
    if has_mvp_review:
        return list(HOME_ACTIONS_WITH_MVP_REVIEW)
    return list(HOME_ACTIONS_WITH_PROJECT)


def project_ids_sent_for_mvp_review(
    db: Session, project_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Projects that already had ``/sendreview`` (BuildJob ``sent_to_client``)."""
    ids = [pid for pid in project_ids if pid]
    if not ids:
        return set()
    rows = db.scalars(
        select(BuildJob.project_id)
        .where(
            BuildJob.project_id.in_(ids),
            BuildJob.status == BuildJobStatus.SENT_TO_CLIENT.value,
        )
        .distinct()
    )
    return set(rows)


def project_has_mvp_review(db: Session, project_id: uuid.UUID) -> bool:
    return project_id in project_ids_sent_for_mvp_review(db, [project_id])


def home_actions_for_projects(
    db: Session, projects: list,
) -> list[str]:
    ids = [p.id for p in projects]
    reviewed = project_ids_sent_for_mvp_review(db, ids)
    return home_actions(project_count=len(projects), has_mvp_review=bool(reviewed))


def attach_mvp_review_flags(db: Session, projects: list) -> dict[uuid.UUID, bool]:
    reviewed = project_ids_sent_for_mvp_review(db, [p.id for p in projects])
    return {p.id: p.id in reviewed for p in projects}
