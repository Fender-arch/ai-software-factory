"""EPIC-06 owner TZ graph console."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.db import Base
from core.models import Project, ProjectStatus
import core.models  # noqa: F401
from core.requirement_console import (
    ConsoleError,
    add_requirement_relation,
    set_requirement_status,
)
from knowledge.repository import KnowledgeRepository
from knowledge.tz_graph import build_tz_graph
from knowledge.types import normalize_requirement_status


def _seed_project(client, *, name="Cafe", uid="9001", product_type="website"):
    created = client.post(
        "/projects",
        json={"name": name, "customer_telegram_id": uid, "product_type": product_type},
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    msg = client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": uid},
        json={"text": "Нужен сайт для кафе: витрина и форма заявки на русском"},
    )
    assert msg.status_code == 201
    return pid, uid


def test_console_static_served(client):
    res = client.get("/console/")
    assert res.status_code == 200
    assert "требован" in res.text.lower()
    assert "новое" in res.text
    assert "foundry-field" in res.text
    js = client.get("/console/app.js")
    assert js.status_code == 200
    assert "estimateHtml" in js.text
    assert "clientEstimateHtml" in js.text
    assert "Оценка стоимости" in js.text
    assert "Смета клиенту" in js.text


def test_console_lists_projects_without_token_in_local_debug(client):
    client.post("/projects", json={"name": "A", "customer_telegram_id": "1"})
    res = client.get("/console/api/projects")
    assert res.status_code == 200
    body = res.json()
    assert any(p["name"] == "A" for p in body)


def test_console_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("CONSOLE_TOKEN", "s3cret")
    get_settings.cache_clear()
    try:
        denied = client.get("/console/api/projects")
        assert denied.status_code == 401
        allowed = client.get(
            "/console/api/projects", headers={"X-Console-Token": "s3cret"}
        )
        assert allowed.status_code == 200
        wrong = client.get(
            "/console/api/projects", headers={"X-Console-Token": "nope"}
        )
        assert wrong.status_code == 401
    finally:
        monkeypatch.delenv("CONSOLE_TOKEN", raising=False)
        get_settings.cache_clear()


def test_tz_graph_stage_topic_requirement(client):
    pid, uid = _seed_project(client)
    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"project", "stage", "topic", "requirement"} <= kinds
    req = next(n for n in graph["nodes"] if n["kind"] == "requirement")
    assert req["parent"].startswith("topic:")
    assert req["status"] == "new"
    assert req["is_new"] is True
    struct = [e for e in graph["edges"] if e["kind"] == "structure"]
    assert any(e["to"] == req["id"] for e in struct)
    parent = next(n for n in graph["nodes"] if n["id"] == req["parent"])
    assert parent["kind"] == "topic"
    stage = next(n for n in graph["nodes"] if n["id"] == parent["parent"])
    assert stage["kind"] == "stage"

    card = client.get(f"/console/api/projects/{pid}/requirements/{req['id']}").json()
    assert card["id"] == req["id"]
    assert card["author"]["id"] == uid
    assert any(h["action"] == "created" for h in card["history"])


def test_tz_graph_includes_delivery_estimate(client):
    pid, _uid = _seed_project(client)
    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    estimate = graph["project"]["estimate"]
    assert estimate
    assert estimate["cost"] > 0
    assert estimate["hours"] > 0
    assert estimate["formatted_cost"]
    assert estimate["formatted_hours"]
    assert estimate["formatted_rate"]
    assert estimate["rationale"]
    assert "must_count" in estimate
    assert estimate["budget_fit_label"]
    client_est = graph["project"]["client_estimate"]
    assert client_est
    assert client_est["cost"] > 0
    assert client_est["method"] == "market_v1"
    assert client_est["sources"]
    assert all("Admin analytics" not in str(src) for src in client_est["sources"])


def test_status_history_and_rejected_requires_reason(client):
    pid, _uid = _seed_project(client)
    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    req_id = next(n["id"] for n in graph["nodes"] if n["kind"] == "requirement")

    bad = client.patch(
        f"/console/api/projects/{pid}/requirements/{req_id}",
        json={"status": "rejected"},
    )
    assert bad.status_code == 400

    processed = client.patch(
        f"/console/api/projects/{pid}/requirements/{req_id}",
        json={"status": "processed"},
    )
    assert processed.status_code == 200
    assert processed.json()["status"] == "processed"
    assert any(h["action"] == "status_change" for h in processed.json()["history"])

    rejected = client.patch(
        f"/console/api/projects/{pid}/requirements/{req_id}",
        json={"status": "rejected", "reason": "дубль с другим пунктом"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reason"] == "дубль с другим пунктом"


def test_console_create_and_edit_requirement_keeps_history(client):
    pid, _uid = _seed_project(client)
    created = client.post(
        f"/console/api/projects/{pid}/requirements",
        json={
            "topic_id": "must_features",
            "description": "Нужна кнопка «Заказать» на главной",
            "priority": "must",
        },
    )
    assert created.status_code == 200
    card = created.json()
    req_id = card["id"]
    assert card["description"] == "Нужна кнопка «Заказать» на главной"
    assert card["topic_id"] == "must_features"
    assert card["status"] == "new"
    assert any(h["action"] == "created" for h in card["history"])

    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    node = next(n for n in graph["nodes"] if n["id"] == req_id)
    assert node["parent"] == "topic:must_features"

    empty = client.post(
        f"/console/api/projects/{pid}/requirements",
        json={"topic_id": "must_features", "description": "   "},
    )
    assert empty.status_code == 400

    edited = client.patch(
        f"/console/api/projects/{pid}/requirements/{req_id}",
        json={"description": "Кнопка «Заказать» ведёт на форму заявки"},
    )
    assert edited.status_code == 200
    assert "форму заявки" in edited.json()["description"]
    updates = [h for h in edited.json()["history"] if h["action"] == "updated"]
    assert updates
    assert "Заказать" in (updates[-1].get("payload") or {}).get("fields", {}).get(
        "description", {}
    ).get("from", "")

    moved = client.patch(
        f"/console/api/projects/{pid}/requirements/{req_id}",
        json={"topic_id": "pages_sections", "priority": "should"},
    )
    assert moved.status_code == 200
    assert moved.json()["topic_id"] == "pages_sections"
    assert moved.json()["priority"] == "should"


def test_depends_on_and_conflicts_with_edge_kinds(client):
    pid, uid = _seed_project(client)
    client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": uid},
        json={"text": "Главный сценарий: гость оставляет заявку, нам приходит уведомление"},
    )
    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    reqs = [n["id"] for n in graph["nodes"] if n["kind"] == "requirement"]
    assert len(reqs) >= 2
    a, b = reqs[0], reqs[1]

    dep = client.post(
        f"/console/api/projects/{pid}/requirements/{a}/relations",
        json={"type": "depends_on", "peer_id": b},
    )
    assert dep.status_code == 200
    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    kinds = {e["kind"] for e in graph["edges"]}
    assert "depends_on" in kinds
    assert "conflicts_with" not in kinds

    conf = client.post(
        f"/console/api/projects/{pid}/requirements/{a}/relations",
        json={"type": "conflicts_with", "peer_id": b},
    )
    assert conf.status_code == 200
    graph = client.get(f"/console/api/projects/{pid}/tz-graph").json()
    edge_kinds = {e["kind"] for e in graph["edges"]}
    assert "depends_on" in edge_kinds
    assert "conflicts_with" in edge_kinds
    statuses = {
        n["id"]: n["status"]
        for n in graph["nodes"]
        if n["kind"] == "requirement" and n["id"] in {a, b}
    }
    assert statuses[a] == "conflict"
    assert statuses[b] == "conflict"
    assert any(
        n["has_conflict"] for n in graph["nodes"] if n["id"] in {a, b}
    )


def test_active_status_maps_to_new_in_projection():
    assert normalize_requirement_status("active") == "new"
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        project = Project(
            name="Legacy", status=ProjectStatus.INTERVIEW, product_type="website"
        )
        db.add(project)
        db.flush()
        kg = KnowledgeRepository(db)
        kg.create_entity(
            project.id,
            "Requirement",
            "Old req",
            status="active",
            payload={
                "description": "Contact form",
                "topic_id": "purpose_problem",
                "stage": "UNDERSTANDING_IDEA",
            },
        )
        graph = build_tz_graph(kg, project)
        req = next(n for n in graph["nodes"] if n["kind"] == "requirement")
        assert req["status"] == "new"
        assert req["is_new"] is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_rejected_without_reason_domain_error():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        project = Project(name="X", status=ProjectStatus.INTERVIEW, product_type="website")
        db.add(project)
        db.flush()
        kg = KnowledgeRepository(db)
        req = kg.create_entity(
            project.id,
            "Requirement",
            "R",
            status="new",
            payload={"description": "x", "topic_id": "roles"},
        )
        with pytest.raises(ConsoleError, match="reason"):
            set_requirement_status(db, project, req.id, "rejected")
        other = kg.create_entity(
            project.id,
            "Requirement",
            "S",
            status="new",
            payload={"description": "y", "topic_id": "access"},
        )
        add_requirement_relation(
            db, project, req.id, rel_type="depends_on", peer_id=other.id
        )
        add_requirement_relation(
            db, project, req.id, rel_type="conflicts_with", peer_id=other.id
        )
        graph = build_tz_graph(kg, project)
        kinds = [e["kind"] for e in graph["edges"]]
        assert kinds.count("depends_on") == 1
        assert kinds.count("conflicts_with") == 1
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_console_icons_cover_tz_topics():
    root = Path(__file__).resolve().parents[1]
    mapping = json.loads((root / "apps/console/icons/map.json").read_text(encoding="utf-8"))
    from discovery.tz_outline import TZ_TOPICS

    missing = [topic.id for topic in TZ_TOPICS if topic.id not in mapping["topics"]]
    assert missing == [], missing
    assert mapping["topics"]["other"]
    used = (
        set(mapping["topics"].values())
        | set(mapping["stages"].values())
        | set(mapping["products"].values())
        | {mapping["fallback"]}
    )
    icons = root / "apps/console/icons"
    missing_files = [name for name in used if not (icons / f"{name}.svg").is_file()]
    assert missing_files == [], missing_files
    for key in (
        "website",
        "telegram_bot",
        "rest_service",
        "ai_automation",
        "mobile_native",
    ):
        assert key in mapping["products"]


def test_console_icon_map_served(client):
    res = client.get("/console/icons/map.json")
    assert res.status_code == 200
    body = res.json()
    assert "purpose_problem" in body["topics"]
    svg = client.get("/console/icons/target.svg")
    assert svg.status_code == 200
    assert b"<svg" in svg.content
    assert b"asf-icon-bg" not in svg.content


def test_console_tz_export_md_docx_pdf(client):
    pid, _uid = _seed_project(client)
    md = client.get(f"/console/api/projects/{pid}/tz-export?format=md")
    assert md.status_code == 200
    text = md.content.decode("utf-8")
    assert "Техническое задание" in text
    assert "Cafe" in text
    assert "attachment" in md.headers.get("content-disposition", "")

    docx = client.get(f"/console/api/projects/{pid}/tz-export?format=docx")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"

    pdf = client.get(f"/console/api/projects/{pid}/tz-export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_console_project_files_upload_download_delete_history(client):
    pid, uid = _seed_project(client)
    attached = client.post(
        f"/projects/{pid}/messages/file",
        params={"customer_telegram_id": uid},
        files={"file": ("brief.txt", io.BytesIO(b"logo and menu photos"), "text/plain")},
    )
    assert attached.status_code == 201

    listed = client.get(f"/console/api/projects/{pid}/files")
    assert listed.status_code == 200
    body = listed.json()
    names = {item["filename"] for item in body["files"]}
    assert "brief.txt" in names
    customer = next(item for item in body["files"] if item["filename"] == "brief.txt")
    assert customer["source"] == "customer"
    assert customer["stage"]
    assert customer["downloadable"] is True
    assert any(h["action"] == "created" for h in body["history"])

    uploaded = client.post(
        f"/console/api/projects/{pid}/files",
        data={"stage": "DATA"},
        files={"file": ("schema.json", io.BytesIO(b'{"tables":1}'), "application/json")},
    )
    assert uploaded.status_code == 200
    bundle = uploaded.json()
    extra = next(item for item in bundle["files"] if item["filename"] == "schema.json")
    assert extra["stage"] == "DATA"
    assert extra["source"] == "console"

    content = client.get(f"/console/api/projects/{pid}/files/{extra['id']}/content")
    assert content.status_code == 200
    assert content.content == b'{"tables":1}'

    deleted = client.delete(f"/console/api/projects/{pid}/files/{extra['id']}")
    assert deleted.status_code == 200
    remaining = {item["filename"] for item in deleted.json()["files"]}
    assert "schema.json" not in remaining
    assert "brief.txt" in remaining
    assert any(
        h["action"] == "deleted" and h["payload"].get("filename") == "schema.json"
        for h in deleted.json()["history"]
    )
    missing = client.get(f"/console/api/projects/{pid}/files/{extra['id']}/content")
    assert missing.status_code == 404
