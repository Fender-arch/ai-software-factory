from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.coordinator import CoordinatorMode
from core.db import Base
from core.models import Project, ProjectStatus
import core.models  # noqa: F401
from knowledge.context import ContextBuilder
from knowledge.coverage import evaluate_coverage, mode_exit_checklist
from knowledge.repository import KnowledgeRepository
from knowledge.traceability import (
    build_trace_forward,
    build_trace_to_task,
    link_derived_from,
    list_requirement_traces,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _project(db) -> Project:
    project = Project(name="KG Demo", status=ProjectStatus.INTERVIEW, product_type="website")
    db.add(project)
    db.flush()
    return project


def test_entity_relation_crud_and_search(db):
    project = _project(db)
    kg = KnowledgeRepository(db)

    msg = kg.create_entity(
        project.id, "Message", "hello", payload={"text": "hello bakery site"}
    )
    req = kg.create_entity(
        project.id,
        "Requirement",
        "Need contact form",
        payload={"title": "form", "description": "Contact form CTA", "priority": "must"},
    )
    rel = link_derived_from(kg, project.id, msg.id, req.id)
    db.commit()

    assert kg.get_entity(req.id, project_id=project.id) is not None
    assert kg.get_relation(rel.id, project_id=project.id) is not None
    assert len(kg.list_relations(project.id, type_="derived_from")) == 1

    hits = kg.search_entities(project.id, "contact")
    assert any(e.id == req.id for e in hits)

    kg.update_entity(req, status="confirmed")
    assert kg.get_entity(req.id).status == "confirmed"

    kg.delete_entity(req, soft=True)
    assert kg.get_entity(req.id).status == "archived"

    with pytest.raises(ValueError):
        kg.create_entity(project.id, "NotAType", "x")

    with pytest.raises(ValueError):
        kg.create_relation(
            project.id, msg.id, req.id, type_="not_a_relation"
        )


def test_trace_message_requirement_decision_task(db):
    project = _project(db)
    kg = KnowledgeRepository(db)

    msg = kg.create_entity(
        project.id, "Message", "We need a landing page", payload={"text": "landing"}
    )
    req = kg.create_entity(
        project.id,
        "Requirement",
        "Landing page",
        payload={
            "title": "landing",
            "description": "Marketing landing with CTA",
            "priority": "must",
            "stage": "FUNCTIONAL",
        },
    )
    link_derived_from(kg, project.id, msg.id, req.id)

    chain = build_trace_to_task(kg, project.id, message_id=msg.id)
    assert chain is not None
    types = [e.type for e in chain.entities]
    assert types == ["Message", "Requirement", "Decision", "Task"]

    # Idempotent stubs
    again = build_trace_to_task(kg, project.id, requirement_id=req.id)
    assert again is not None
    assert len(kg.list_entities(project.id, type_="Decision")) == 1
    assert len(kg.list_entities(project.id, type_="Task")) == 1

    forward = build_trace_forward(kg, project.id, req)
    assert [e.type for e in forward.entities] == ["Requirement", "Decision", "Task"]

    traces = list_requirement_traces(kg, project.id)
    assert len(traces) == 1
    assert traces[0]["messages"][0]["id"] == str(msg.id)
    assert traces[0]["tasks"]


def test_context_builder_is_mode_scoped(db):
    project = _project(db)
    kg = KnowledgeRepository(db)
    kg.create_entity(project.id, "Project", project.name, payload={"discovery_stage": "USERS"})
    kg.create_entity(
        project.id,
        "Requirement",
        "Users are bakery customers",
        payload={
            "title": "users",
            "description": "Primary audience is bakery customers with CTA to email",
            "priority": "must",
            "stage": "USERS",
        },
    )
    kg.create_entity(
        project.id,
        "Task",
        "Build form",
        payload={"title": "Build form"},
    )
    db.commit()

    discovery_ctx = ContextBuilder(db).build(CoordinatorMode.DISCOVERY, project)
    assert "recent_messages" in discovery_ctx
    assert "requirements" in discovery_ctx
    assert "tasks" not in discovery_ctx  # discovery does not get task dump
    assert discovery_ctx["mode"] == "discovery"
    assert "coverage" in discovery_ctx

    planner_ctx = ContextBuilder(db).build(CoordinatorMode.PLANNER, project)
    assert "tasks" in planner_ctx
    assert "traces" in planner_ctx
    assert "recent_messages" not in planner_ctx


def test_coverage_checklist_helpers(db):
    project = _project(db)
    kg = KnowledgeRepository(db)
    kg.create_entity(
        project.id,
        "Requirement",
        "Audience CTA",
        payload={
            "title": "cta",
            "description": "Primary CTA is contact form for bakery customers",
            "priority": "must",
            "stage": "USERS",
        },
    )
    kg.create_entity(
        project.id,
        "Requirement",
        "Pages",
        payload={
            "title": "pages",
            "description": "Home, menu, and contact page sections",
            "priority": "must",
            "stage": "FUNCTIONAL",
        },
    )
    db.commit()

    report = evaluate_coverage(kg, project.id, product_type="website")
    assert report.requirement_count == 2
    covered_ids = {i.id for i in report.items if i.covered}
    assert "audience_cta" in covered_ids
    assert "pages_sections" in covered_ids
    assert report.ratio > 0

    checks = mode_exit_checklist(
        "discovery",
        coverage=report,
        open_question_count=0,
        has_draft_tz=False,
    )
    by_id = {c["id"]: c for c in checks}
    assert by_id["has_requirements"]["ok"] is True
    assert "quality_floor" in by_id
    quality_ids = {i.id for i in report.quality_items}
    assert "measurable_success" in quality_ids
    assert "scope_bounded" in quality_ids
    assert "testable_requirements" in quality_ids
    assert report.as_dict()["quality_ok"] is False


def test_relation_rejects_cross_project(db):
    a = _project(db)
    b = Project(name="Other", status=ProjectStatus.NEW, product_type="website")
    db.add(b)
    db.flush()
    kg = KnowledgeRepository(db)
    ea = kg.create_entity(a.id, "Message", "a")
    eb = kg.create_entity(b.id, "Requirement", "b", payload={"title": "x", "description": "y", "priority": "must"})
    with pytest.raises(ValueError, match="belong to the project"):
        kg.create_relation(a.id, ea.id, eb.id, type_="derived_from")


def test_discovery_api_includes_coverage(client):
    created = client.post(
        "/projects", json={"name": "Covered Site", "product_type": "website"}
    )
    project_id = created.json()["id"]
    client.post(
        f"/projects/{project_id}/messages",
        json={
            "text": (
                "Marketing website for bakery customers with contact form CTA "
                "and home/menu pages"
            )
        },
    )
    result = client.post(f"/projects/{project_id}/coordinator/discovery")
    assert result.status_code == 200
    body = result.json()
    assert "coverage" in body["output"]
    assert "exit_checklist" in body["output"]
    assert body["output"]["coverage"]["requirement_count"] >= 1
