"""DEC-015: intro before tech, brief-file merge into the KG."""

from __future__ import annotations

import io
import uuid

from apps.api.main import app
from core.db import get_db
from core.models import Project
from discovery.brief_ingest import heuristic_extract, looks_like_brief_document
from discovery.fsm import DiscoveryStage
from discovery.stakeholders import parse_stakeholder_text
from discovery.questions import first_topic
from discovery.tz_outline import remaining_topics, topic_by_id
from knowledge.repository import KnowledgeRepository
from tests.test_discovery import INTRO_ANSWER, _complete_intro


BRIEF_MD = """# Постановка на сайт салона

## Цель
Нужен сайт записи клиентов в салон красоты с напоминаниями.

## Обязательные функции
Календарь слотов, форма заявки, напоминание в Telegram за день.

## SLA ночной поддержки
Дежурный отвечает в течение 15 минут ночью — это сверх обычных разделов ТЗ.
"""


def _answered(kg, project) -> set[str]:
    entities = kg.list_entities(project.id, type_="Project")
    state = dict(entities[0].payload or {})
    return set(state.get("answered_topics") or []) | set(state.get("escalated_topics") or [])


def test_first_topic_is_customer_intro():
    assert first_topic().id == "customer_intro"
    leftover = remaining_topics(None, done_ids=set())
    assert leftover[0].id == "customer_intro"
    assert leftover[1].id == "have_brief"
    purpose = next(t for t in leftover if t.id == "purpose_problem")
    assert leftover.index(topic_by_id("customer_intro")) < leftover.index(purpose)


def test_parse_intro_facts_and_individual():
    facts = parse_stakeholder_text(
        "Меня зовут Дмитрий, +7 900 111-22-33, dima@example.com, "
        "компания Пекарня у дома, отрасль общепит, я владелец"
    )
    assert facts.display_name.startswith("Дмитрий")
    assert facts.phone
    assert facts.email.startswith("dima@")
    assert "Пекарня" in facts.organization_name
    assert "общепит" in facts.industry
    assert facts.role == "владелец"
    assert facts.sufficient()

    solo = parse_stakeholder_text(
        "Анна, физлицо, без названия компании, @anna_demo",
        choice_ids=["intro_individual"],
    )
    assert solo.has_name()
    assert solo.is_individual
    assert solo.has_contact()


def test_intro_before_tech(client):
    created = client.post("/projects", json={"name": "IntroOrder", "product_type": "website"})
    pid = created.json()["id"]
    ws = client.get(f"/projects/{pid}/workspace", params={"mode": "create"})
    assert ws.status_code == 200
    data = ws.json()
    assert data.get("topic_id") == "customer_intro"
    assert data.get("discovery_stage") == DiscoveryStage.CUSTOMER_INTRO.value
    blob = " ".join(m["text"] for m in data["messages"])
    assert "познакоми" in blob.lower()
    assert "сайт, бот" not in blob.lower() or "сначала" in blob.lower()

    intro = client.post(f"/projects/{pid}/messages", json={"text": INTRO_ANSWER})
    assert intro.status_code == 201
    assert intro.json().get("topic_id") == "have_brief"
    assert intro.json()["discovery_stage"] == DiscoveryStage.CUSTOMER_INTRO.value
    assert intro.json()["project_status"] != "WAITING_OWNER"

    no_brief = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Нет готовой постановки — давайте в разговоре"},
    )
    assert no_brief.json().get("topic_id") == "purpose_problem"
    assert no_brief.json()["discovery_stage"] == DiscoveryStage.UNDERSTANDING_IDEA.value
    reply = (no_brief.json().get("discovery_reply") or "").lower()
    assert "проблем" in reply or "иде" in reply or "задач" in reply


def test_file_ingest_merges_entities_and_topics(client):
    created = client.post(
        "/projects",
        json={
            "name": "BriefMerge",
            "product_type": "website",
            "customer_telegram_id": "88001",
        },
    )
    pid = created.json()["id"]
    _complete_intro(client, pid, have_brief=True)

    attached = client.post(
        f"/projects/{pid}/messages/file",
        params={"customer_telegram_id": "88001"},
        files={"file": ("salon-brief.md", io.BytesIO(BRIEF_MD.encode("utf-8")), "text/markdown")},
    )
    assert attached.status_code == 201
    body = attached.json()
    reply = body.get("discovery_reply") or ""
    assert "разобрал" in reply.lower() or "постановк" in reply.lower()
    assert BRIEF_MD.strip() not in reply
    assert body.get("topic_id") != "have_brief"
    assert body["project_status"] != "WAITING_OWNER"

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        project = db.get(Project, uuid.UUID(pid))
        kg = KnowledgeRepository(db)
        customers = kg.list_entities(project.id, type_="Customer")
        orgs = kg.list_entities(project.id, type_="Organization")
        assert customers, "Customer entity must be stored from intro"
        assert orgs, "Organization entity must be stored from intro"
        assert "Петров" in (customers[0].payload or {}).get("display_name", "") or "Петров" in customers[0].name
        assert (orgs[0].payload or {}).get("name")
        answered = _answered(kg, project)
        assert "have_brief" in answered
        assert "purpose_problem" in answered
        assert "must_features" in answered
        reqs = kg.list_entities(project.id, type_="Requirement")
        topics = {str((e.payload or {}).get("topic_id") or "") for e in reqs}
        assert "purpose_problem" in topics
        assert any(tid.startswith("custom:") for tid in topics)
    finally:
        db.close()


def test_empty_topics_get_follow_up_after_brief(client):
    created = client.post(
        "/projects",
        json={"name": "BriefGaps", "product_type": "website", "customer_telegram_id": "88002"},
    )
    pid = created.json()["id"]
    _complete_intro(client, pid, have_brief=True)
    attached = client.post(
        f"/projects/{pid}/messages/file",
        params={"customer_telegram_id": "88002"},
        files={"file": ("salon-brief.md", io.BytesIO(BRIEF_MD.encode("utf-8")), "text/markdown")},
    )
    body = attached.json()
    reply = body.get("discovery_reply") or ""
    assert "не хватает" in reply.lower() or "уточн" in reply.lower()
    leftover_id = body.get("topic_id")
    assert leftover_id not in {None, "have_brief", "purpose_problem", "must_features"}
    assert leftover_id != "customer_intro"


def test_brief_overflow_creates_new_topics():
    from discovery.tz_outline import OutlinePlan, resolve_active_topics

    plan = OutlinePlan()
    topics = resolve_active_topics("website", plan=plan)
    mapped, overflow = heuristic_extract(BRIEF_MD, topics=topics)
    assert "purpose_problem" in mapped
    assert "must_features" in mapped
    assert overflow
    assert any("SLA" in title or "поддерж" in title.lower() for title, _ in overflow)
    assert looks_like_brief_document(f"[Файл: x.md]\n{BRIEF_MD}")
