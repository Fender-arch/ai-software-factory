"""Mini App home hub buttons: 0 projects / project without MVP / MVP review sent."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from core.db import Base, get_db
from core.miniapp_home import (
    HOME_ACTIONS_EMPTY,
    HOME_ACTIONS_WITH_MVP_REVIEW,
    HOME_ACTIONS_WITH_PROJECT,
    attach_mvp_review_flags,
    home_actions,
    home_actions_for_projects,
    project_has_mvp_review,
)
from core.models import BuildJob, BuildJobStatus, Project, ProjectStatus
import core.models  # noqa: F401


def test_home_actions_matrix():
    assert home_actions(project_count=0, has_mvp_review=False) == list(HOME_ACTIONS_EMPTY)
    assert home_actions(project_count=0, has_mvp_review=True) == list(HOME_ACTIONS_EMPTY)
    assert home_actions(project_count=1, has_mvp_review=False) == list(
        HOME_ACTIONS_WITH_PROJECT
    )
    assert home_actions(project_count=3, has_mvp_review=False) == list(
        HOME_ACTIONS_WITH_PROJECT
    )
    assert home_actions(project_count=1, has_mvp_review=True) == list(
        HOME_ACTIONS_WITH_MVP_REVIEW
    )


def test_mvp_review_flag_is_sent_to_client_not_ready():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    empty = Project(name="None", status=ProjectStatus.WAITING_CUSTOMER)
    ready = Project(name="ReadyOnly", status=ProjectStatus.READY)
    built = Project(name="Built", status=ProjectStatus.READY)
    sent = Project(name="Sent", status=ProjectStatus.READY)
    db.add_all([empty, ready, built, sent])
    db.flush()
    db.add(
        BuildJob(
            project_id=built.id,
            status=BuildJobStatus.READY_FOR_CLIENT.value,
        )
    )
    db.add(
        BuildJob(
            project_id=sent.id,
            status=BuildJobStatus.SENT_TO_CLIENT.value,
        )
    )
    db.flush()

    flags = attach_mvp_review_flags(db, [empty, ready, built, sent])
    assert flags[empty.id] is False
    assert flags[ready.id] is False
    assert flags[built.id] is False
    assert flags[sent.id] is True
    assert project_has_mvp_review(db, ready.id) is False
    assert project_has_mvp_review(db, sent.id) is True
    assert home_actions_for_projects(db, []) == list(HOME_ACTIONS_EMPTY)
    assert home_actions_for_projects(db, [empty, ready, built]) == list(
        HOME_ACTIONS_WITH_PROJECT
    )
    assert home_actions_for_projects(db, [empty, sent]) == list(
        HOME_ACTIONS_WITH_MVP_REVIEW
    )
    db.close()


def test_list_projects_hub_matrix_via_api(client):
    uid = "61001"
    empty = client.get("/projects", params={"customer_telegram_id": uid})
    assert empty.status_code == 200
    assert empty.json() == []
    assert home_actions(project_count=0, has_mvp_review=False) == ["create"]

    created = client.post(
        "/projects",
        json={"name": "Без MVP", "customer_telegram_id": uid},
    )
    assert created.status_code == 201
    assert created.json()["mvp_review_sent"] is False
    pid = created.json()["id"]

    listed = client.get("/projects", params={"customer_telegram_id": uid})
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == pid
    assert body[0]["mvp_review_sent"] is False
    assert home_actions(project_count=1, has_mvp_review=False) == [
        "create",
        "change",
    ]

    one = client.get(f"/projects/{pid}")
    assert one.status_code == 200
    assert one.json()["mvp_review_sent"] is False

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        row = db.get(Project, uuid.UUID(pid))
        assert row is not None
        row.status = ProjectStatus.READY
        db.add(
            BuildJob(
                project_id=row.id,
                status=BuildJobStatus.READY_FOR_CLIENT.value,
            )
        )
        db.commit()
    finally:
        db.close()

    still = client.get("/projects", params={"customer_telegram_id": uid})
    assert still.json()[0]["mvp_review_sent"] is False
    assert still.json()[0]["status"] == "READY"

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        db.add(
            BuildJob(
                project_id=uuid.UUID(pid),
                status=BuildJobStatus.SENT_TO_CLIENT.value,
            )
        )
        db.commit()
    finally:
        db.close()

    reviewed = client.get("/projects", params={"customer_telegram_id": uid})
    assert reviewed.json()[0]["mvp_review_sent"] is True
    assert client.get(f"/projects/{pid}").json()["mvp_review_sent"] is True
    assert home_actions(project_count=1, has_mvp_review=True) == [
        "create",
        "change",
        "feedback",
    ]


def test_miniapp_home_js_button_matrix(client):
    html = client.get("/miniapp/")
    assert html.status_code == 200
    assert 'data-action="create"' in html.text
    assert 'data-action="change"' in html.text
    assert 'data-action="feedback"' in html.text
    assert "Создать проект" in html.text
    assert "Изменить проект" in html.text
    assert "Замечания к реализации" in html.text
    assert 'data-action="change" class="btn hidden"' in html.text
    assert 'data-action="feedback" class="btn hidden"' in html.text

    js = client.get("/miniapp/app.js")
    assert js.status_code == 200
    assert "HOME_ACTIONS" in js.text
    assert 'empty: ["create"]' in js.text
    assert 'withProject: ["create", "change"]' in js.text
    assert 'withMvpReview: ["create", "change", "feedback"]' in js.text
    assert "homeActionsFromProjects" in js.text
    assert "mvp_review_sent" in js.text
    assert "applyHomeActions" in js.text
    assert "refreshHome" in js.text
    assert 'state.listMode === "feedback"' in js.text
    assert "Пока нет проектов с MVP на проверке." in js.text
