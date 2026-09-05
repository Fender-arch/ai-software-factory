"""DEC-013 MVP Factory + Intervention Queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.db import Base
from core.factory import (
    FactoryError,
    create_mvp_job,
    expire_stale_interventions,
    factory_snapshot,
    latest_build_job,
    list_interventions,
    peek_secret_for_executor,
    resolve_intervention,
)
from core.models import (
    BuildJobStatus,
    Intervention,
    Project,
    ProjectStatus,
)
import core.models  # noqa: F401
from core.mvp_slice import select_mvp_requirements
from core.secrets_box import seal_secret, unseal_secret
from core.services import get_project
from knowledge.repository import KnowledgeRepository
from tests.test_mvp_generation import _reach_waiting_owner


def _approve(client, project_id: str) -> None:
    res = client.post(f"/projects/{project_id}/hitl", json={"action": "approve"})
    assert res.status_code == 200
    assert res.json()["project_status"] == "READY"


def test_create_mvp_requires_owner_approve(client):
    created = client.post("/projects", json={"name": "Too Soon", "product_type": "website"})
    pid = created.json()["id"]
    denied = client.post(f"/console/api/projects/{pid}/mvp", json={})
    assert denied.status_code == 400
    assert "READY" in denied.json()["detail"]


def test_website_mvp_job_queue_and_send(client):
    project_id = _reach_waiting_owner(client)
    before = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    assert before.status_code == 400

    _approve(client, project_id)
    created = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    assert created.status_code == 200
    body = created.json()
    assert body["can_create"] is True
    assert body["job"]["status"] == BuildJobStatus.WAITING_INTERVENTION.value
    assert body["job"]["executor"] == "stub"
    kinds = {i["kind"] for i in body["interventions"]}
    assert "dns" in kinds
    open_iv = next(i for i in body["interventions"] if i["status"] == "open")
    assert open_iv["answer_type"] == "text"
    assert open_iv["has_answer"] is False

    tz = client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.status_code == 200

    resolved = client.post(
        f"/console/api/interventions/{open_iv['id']}/resolve",
        json={"answer": "локально, без домена"},
    )
    assert resolved.status_code == 200
    snap = resolved.json()
    assert snap["job"]["status"] == BuildJobStatus.READY_FOR_CLIENT.value
    assert snap["can_send"] is True
    assert snap["job"]["deep_link"]

    sent = client.post(f"/console/api/projects/{project_id}/mvp/send-to-client")
    assert sent.status_code == 200
    assert sent.json()["job"]["status"] == BuildJobStatus.SENT_TO_CLIENT.value
    assert sent.json()["can_send"] is False

    workspace = client.get(f"/projects/{project_id}/workspace")
    assert workspace.status_code == 200
    texts = [m["text"] for m in workspace.json()["messages"]]
    assert any("review" in t.lower() or "замечан" in t.lower() for t in texts)


def test_telegram_bot_secret_stays_out_of_kg(client):
    created = client.post(
        "/projects", json={"name": "Shop Bot", "product_type": "telegram_bot"}
    )
    from tests.test_discovery import _drive_discovery_to_owner

    project_id = created.json()["id"]
    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"
    _approve(client, project_id)

    job = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    assert job.status_code == 200
    secret_iv = next(
        i for i in job.json()["interventions"] if i["kind"] == "telegram_token"
    )
    assert secret_iv["answer_type"] == "secret"
    secret_value = "123456:FAKE-BOT-TOKEN-FOR-TEST"

    resolved = client.post(
        f"/console/api/interventions/{secret_iv['id']}/resolve",
        json={"answer": secret_value},
    )
    assert resolved.status_code == 200
    shown = next(i for i in resolved.json()["interventions"] if i["id"] == secret_iv["id"])
    assert shown["has_answer"] is True
    assert shown["answer_preview"] is None
    assert secret_value not in str(resolved.json())

    entities = client.get(f"/console/api/projects/{project_id}/tz-graph")
    assert entities.status_code == 200
    assert secret_value not in entities.text


def test_in_mvp_flag_and_must_fallback():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    project = Project(name="Slice", status=ProjectStatus.READY, product_type="website")
    db.add(project)
    db.flush()
    kg = KnowledgeRepository(db)
    must = kg.create_entity(
        project.id, "Requirement", "Must page", payload={"priority": "must"}
    )
    could = kg.create_entity(
        project.id, "Requirement", "Could extra", payload={"priority": "could"}
    )
    picked = select_mvp_requirements(kg.list_entities(project.id, type_="Requirement"))
    assert [e.id for e in picked] == [must.id]

    kg.update_entity(could, payload={"priority": "could", "in_mvp": True})
    kg.update_entity(must, payload={"priority": "must", "in_mvp": False})
    picked2 = select_mvp_requirements(kg.list_entities(project.id, type_="Requirement"))
    assert [e.id for e in picked2] == [could.id]
    db.close()


def test_client_confirm_hook_blocks_when_estimate_unconfirmed(client):
    project_id = _reach_waiting_owner(client)
    _approve(client, project_id)
    # Simulate DEC-012 artifact that is not confirmed yet.
    engine = client.app.dependency_overrides  # keep lint quiet; use graph write via API
    from core.db import get_db

    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        project = get_project(db, project_id)
        kg = KnowledgeRepository(db)
        kg.create_entity(
            project.id,
            "Artifact",
            "Client estimate",
            payload={"kind": "client_estimate", "confirmed": False},
        )
        db.commit()
    finally:
        db.close()

    blocked = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    assert blocked.status_code == 400
    assert "смет" in blocked.json()["detail"].lower() or "confirm" in blocked.json()["detail"]


def test_secret_box_roundtrip(monkeypatch):
    monkeypatch.setenv("ASF_INTERVENTION_KEY", "test-key-please-rotate")
    get_settings.cache_clear()
    token = seal_secret("bot-token-value")
    assert "bot-token-value" not in token
    assert unseal_secret(token) == "bot-token-value"
    get_settings.cache_clear()


def test_expired_intervention_cannot_resolve(client):
    project_id = _reach_waiting_owner(client)
    _approve(client, project_id)
    created = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    iid = created.json()["interventions"][0]["id"]

    from core.db import get_db

    db = next(client.app.dependency_overrides[get_db]())
    try:
        row = db.get(Intervention, uuid.UUID(str(iid)))
        row.ttl_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
        n = expire_stale_interventions(db, row.project_id)
        assert n == 1
        db.commit()
        try:
            resolve_intervention(db, iid, "too late")
            assert False, "should expire"
        except FactoryError as exc:
            assert "истёк" in str(exc) or "expire" in str(exc).lower()
    finally:
        db.close()


def test_reuse_active_job(client):
    project_id = _reach_waiting_owner(client)
    _approve(client, project_id)
    first = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    second = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    assert first.json()["job"]["id"] == second.json()["job"]["id"]
    assert "активн" in (second.json().get("message") or "").lower()


def test_console_static_mentions_factory(client):
    html = client.get("/console/")
    assert html.status_code == 200
    js = client.get("/console/app.js")
    assert "Создать MVP" in js.text
    assert "Intervention Queue" in js.text
    assert "Отправить клиенту на review" in js.text


def test_owner_actor_required_on_telegram_path(client, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "999001")
    get_settings.cache_clear()
    project_id = _reach_waiting_owner(client)
    approved = client.post(
        f"/projects/{project_id}/hitl",
        json={"action": "approve", "actor_telegram_id": "999001"},
    )
    assert approved.status_code == 200
    from core.db import get_db

    db = next(client.app.dependency_overrides[get_db]())
    try:
        project = get_project(db, project_id)
        try:
            create_mvp_job(db, project, actor_telegram_id="111")
            assert False, "non-owner must fail"
        except Exception as exc:
            assert "owner" in str(exc).lower()
        snap = create_mvp_job(db, project, actor_telegram_id="999001")
        assert snap.job is not None
        db.commit()
    finally:
        db.close()
        get_settings.cache_clear()
        monkeypatch.delenv("OWNER_TELEGRAM_ID", raising=False)
        get_settings.cache_clear()


def test_peek_secret_does_not_write_plaintext_to_job(client):
    created = client.post(
        "/projects", json={"name": "Secret Peek", "product_type": "telegram_bot"}
    )
    from tests.test_discovery import _drive_discovery_to_owner

    project_id = created.json()["id"]
    _drive_discovery_to_owner(client, project_id)
    _approve(client, project_id)
    job = client.post(f"/console/api/projects/{project_id}/mvp", json={})
    iid = next(i["id"] for i in job.json()["interventions"] if i["kind"] == "telegram_token")
    secret = "super-secret-token-xyz"
    client.post(f"/console/api/interventions/{iid}/resolve", json={"answer": secret})

    from core.db import get_db

    db = next(client.app.dependency_overrides[get_db]())
    try:
        row = db.get(Intervention, uuid.UUID(str(iid)))
        assert row.answer_ciphertext
        assert secret not in (row.answer_ciphertext or "")
        assert secret not in str(row.payload)
        assert peek_secret_for_executor(row) == secret
        build = latest_build_job(db, row.project_id)
        assert secret not in str(build.payload)
        assert factory_snapshot(db, get_project(db, project_id)).job["status"] in {
            BuildJobStatus.READY_FOR_CLIENT.value,
            BuildJobStatus.RUNNING.value,
        }
        open_left = list_interventions(db, row.project_id, status="open")
        assert open_left == []
    finally:
        db.close()
