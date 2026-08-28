from discovery.fsm import DiscoveryStage, advance_stage, project_status_for_stage, regress_stage
from discovery.literacy import ITLiteracy, infer_literacy
from discovery.questions import question_for
from core.models import ProjectStatus
import io


def _content_reply_for_topic(topic_id: str | None, fallback_index: int) -> str:
    replies = {
        "public_identity": (
            "Студия UNI4IT — IT-услуги, слоган «Универсальные решения для IT»"
        ),
        "offer_catalog": (
            "Сайты и лендинги: витрина услуг. Telegram-боты под задачу. "
            "Портфолио: три ссылки пришлю к макету."
        ),
        "visitor_cta": "Форма заявки: имя, контакт, сообщение",
        "brand_assets": "Простой аккуратный вид, без брендбука",
        "design_references": "Референсов нет — ориентируемся на выбранный стиль ниже",
        "design_direction": "Спокойный, лаконичный, много воздуха",
        "integrations": "Заявки приходят мне в этот Telegram",
        "ops_constraints": "Не знаю про серверы — пусть предложит разработчик",
        "interaction_model": "Только Mini App — чат бота не нужен",
    }
    if topic_id and topic_id in replies:
        return replies[topic_id]
    return (
        f"Достаточно деталей для раздела MVP номер {fallback_index + 1}: "
        "фиксируем ответ заказчика для первой версии."
    )


def _drive_discovery_to_owner(client, project_id: str):
    last = None
    for i in range(80):
        if last is not None:
            body = last.json()
            if body["project_status"] == "WAITING_OWNER":
                return last
            topic = str(body.get("topic_id") or "")
            if body.get("discovery_stage") == DiscoveryStage.REVIEW.value:
                if topic.startswith("clarify:") or topic.startswith("closing:"):
                    last = client.post(
                        f"/projects/{project_id}/messages",
                        json={"text": "1"},
                    )
                    assert last.status_code == 201
                    continue
                last = client.post(
                    f"/projects/{project_id}/messages",
                    json={"text": "готово"},
                )
                assert last.status_code == 201
                return last
        topic = last.json().get("topic_id") if last is not None else None
        last = client.post(
            f"/projects/{project_id}/messages",
            json={"text": _content_reply_for_topic(topic, i)},
        )
        assert last.status_code == 201
    raise AssertionError("Discovery did not reach WAITING_OWNER")


def _seek_topic(client, project_id: str, target: str, limit: int = 60, start=None):
    last = start
    for i in range(limit):
        current = last.json().get("topic_id") if last is not None else None
        if current == target:
            return last
        last = client.post(
            f"/projects/{project_id}/messages",
            json={"text": _content_reply_for_topic(current, i)},
        )
        assert last.status_code == 201
    raise AssertionError(f"Discovery did not reach topic {target}")


def test_fsm_advance_and_regress():
    stage = DiscoveryStage.UNDERSTANDING_IDEA
    stage = advance_stage(stage)
    assert stage == DiscoveryStage.BUSINESS_CONTEXT
    stage = regress_stage(stage)
    assert stage == DiscoveryStage.UNDERSTANDING_IDEA
    assert project_status_for_stage(DiscoveryStage.REVIEW) == ProjectStatus.ANALYZING
    assert (
        project_status_for_stage(DiscoveryStage.READY_FOR_OWNER)
        == ProjectStatus.WAITING_OWNER
    )


def test_literacy_detects_high_and_does_not_downgrade():
    high = infer_literacy("We need a REST API with JWT and OpenAPI docs")
    assert high == ITLiteracy.HIGH
    still_high = infer_literacy("just a simple idea", previous=high)
    assert still_high == ITLiteracy.HIGH
    low = infer_literacy("I want something for my customers to leave requests")
    assert low == ITLiteracy.LOW


def test_questions_adapt_to_literacy():
    low_q = question_for(
        DiscoveryStage.FUNCTIONAL,
        ITLiteracy.LOW,
        product_type="website",
        topic_id="must_features",
    )
    high_q = question_for(
        DiscoveryStage.FUNCTIONAL,
        ITLiteracy.HIGH,
        product_type="website",
        topic_id="must_features",
    )
    pages_q = question_for(
        DiscoveryStage.FUNCTIONAL,
        ITLiteracy.LOW,
        product_type="website",
        topic_id="pages_sections",
    )
    assert "обязательно" in low_q.lower() or "первой версии" in low_q.lower()
    assert "must/should" in high_q.lower() or "приёмк" in high_q.lower()
    assert "CTA" in pages_q or "страниц" in pages_q.lower() or "кнопк" in pages_q.lower()


def test_tz_outline_includes_commercial_intake():
    from discovery.tz_outline import topics_for

    ids = [topic.id for topic in topics_for("website")]
    for topic_id in ("timeline", "budget", "contacts", "preferred_contact", "promotion", "legal_compliance"):
        assert topic_id in ids
    assert ids.index("out_of_scope") < ids.index("timeline") < ids.index("roles")


def test_discovery_interview_extracts_requirements(client):
    created = client.post(
        "/projects",
        json={"name": "Booking", "product_type": "telegram_bot"},
    )
    project_id = created.json()["id"]

    msg = client.post(
        f"/projects/{project_id}/messages",
        json={
            "text": (
                "Need a Telegram bot for salon booking with reminders. "
                "Users pick a time slot."
            )
        },
    )
    assert msg.status_code == 201
    body = msg.json()
    assert body["discovery_reply"]
    assert body["discovery_stage"] == DiscoveryStage.UNDERSTANDING_IDEA.value
    assert body["project_status"] == ProjectStatus.WAITING_CUSTOMER.value
    assert body.get("discovery_choices")

    got = client.get(f"/projects/{project_id}")
    assert got.json()["status"] == "WAITING_CUSTOMER"
    assert got.json()["product_type"] == "telegram_bot"


def test_discovery_reaches_draft_tz(client):
    created = client.post("/projects", json={"name": "Site MVP", "product_type": "website"})
    project_id = created.json()["id"]
    last = _drive_discovery_to_owner(client, project_id)

    assert last is not None
    assert last.json()["project_status"] == "WAITING_OWNER"
    assert last.json()["discovery_stage"] == DiscoveryStage.READY_FOR_OWNER.value

    project = client.get(f"/projects/{project_id}").json()
    assert project["status"] == "WAITING_OWNER"
    assert project["product_type"] == "website"

    tz = client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.status_code == 200
    content = tz.json()["content"]
    assert "Draft TZ" in content
    assert "TZ sections" in content
    assert "Implementation timeline" in content
    assert "Budget" in content
    assert "Contact details" in content
    assert "Preferred contact channel" in content
    assert "Open questions" in content
    assert "FR-" in content
    assert "SC-" in content
    assert "User stories" in content
    assert "Given" in content

    snap = client.post(f"/projects/{project_id}/coordinator/discovery")
    assert snap.status_code == 200
    output = snap.json()["output"]
    assert output["discovery_stage"] == "READY_FOR_OWNER"
    assert output["artifact_id"]


def test_owner_review_records_customer_supplements(client):
    created = client.post("/projects", json={"name": "Site MVP", "product_type": "website"})
    project_id = created.json()["id"]
    _drive_discovery_to_owner(client, project_id)

    extra = "Нужна ещё кнопка «Позвонить» на главной"
    res = client.post(
        f"/projects/{project_id}/messages",
        json={"text": extra, "role": "customer"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["project_status"] == "WAITING_OWNER"
    assert body["discovery_stage"] == DiscoveryStage.READY_FOR_OWNER.value
    assert "зафиксир" in (body["discovery_reply"] or "").lower()

    project = client.get(f"/projects/{project_id}").json()
    assert project["status"] == "WAITING_OWNER"

    content = client.get(f"/projects/{project_id}/artifacts/draft-tz").json()["content"]
    assert extra in content
    assert "Customer supplements after review" in content


def test_voice_path_runs_discovery(client):
    created = client.post("/projects", json={"name": "Voice Disco"})
    project_id = created.json()["id"]
    response = client.post(
        f"/projects/{project_id}/messages/voice",
        files={"file": ("note.ogg", b"fake-audio-bytes", "audio/ogg")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "stub transcript" in data["text"]
    assert data["discovery_reply"]
    assert data["discovery_stage"] == DiscoveryStage.UNDERSTANDING_IDEA.value


def test_discovery_does_not_finalize_after_one_answer(client):
    created = client.post("/projects", json={"name": "Early", "product_type": "website"})
    pid = created.json()["id"]
    msg = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Нужен сайт визитка для пекарни с формой заявки"},
    )
    body = msg.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert body["discovery_stage"] != DiscoveryStage.READY_FOR_OWNER.value
    assert "Раздел ТЗ" in (body["discovery_reply"] or "")


def test_discovery_pause_keeps_interview_open(client):
    created = client.post("/projects", json={"name": "Pause", "product_type": "website"})
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/messages", json={"text": "Идея: сайт с заявками"})
    paused = client.post(f"/projects/{pid}/messages", json={"text": "пауза"})
    body = paused.json()
    assert body["paused"] is True
    assert body["project_status"] == "WAITING_CUSTOMER"
    assert body["discovery_stage"] != DiscoveryStage.READY_FOR_OWNER.value
    resumed = client.post(f"/projects/{pid}/messages", json={"text": "продолжить"})
    assert resumed.json()["paused"] is False
    assert "Раздел ТЗ" in (resumed.json()["discovery_reply"] or "")


def test_discovery_ready_too_early_is_refused(client):
    created = client.post("/projects", json={"name": "TooSoon", "product_type": "website"})
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/messages", json={"text": "Сайт для кафе"})
    ready = client.post(f"/projects/{pid}/messages", json={"text": "готово"})
    body = ready.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert "рано" in (body["discovery_reply"] or "").lower()


def test_discovery_discuss_with_developer_creates_open_question(client):
    created = client.post("/projects", json={"name": "Discuss", "product_type": "website"})
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Обсудить с разработчиком, что нужно зафиксировать"},
    )
    assert first.status_code == 201
    assert first.json()["project_status"] != "WAITING_OWNER"
    kg = client.post(f"/projects/{pid}/coordinator/discovery")
    coverage = kg.json()["output"]["coverage"]
    assert coverage["open_question_count"] >= 1


def test_discovery_choice_sets_product_shape(client):
    created = client.post("/projects", json={"name": "Shape"})
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/messages", json={"text": "Нужно автоматизировать заявки"})
    shaped = client.post(
        f"/projects/{pid}/messages",
        json={"text": "2. Telegram-бот"},
    )
    assert shaped.status_code == 201
    project = client.get(f"/projects/{pid}").json()
    assert project["product_type"] == "telegram_bot"


def test_discovery_multi_choice_covers_out_of_scope(client):
    created = client.post(
        "/projects", json={"name": "MultiScope", "product_type": "website"}
    )
    pid = created.json()["id"]
    fourth = None
    for i in range(4):
        fourth = client.post(
            f"/projects/{pid}/messages",
            json={"text": f"Подробный ответ по разделу MVP номер {i + 1} для пекарни."},
        )
        assert fourth.status_code == 201
        assert fourth.json()["project_status"] != "WAITING_OWNER"
    assert fourth is not None
    assert fourth.json().get("allow_multiple") is True
    assert "Вне объёма" in (fourth.json().get("discovery_reply") or "")

    fifth = client.post(
        f"/projects/{pid}/messages",
        json={"text": "1, 3"},
    )
    assert fifth.status_code == 201
    body = fifth.json()
    assert body["project_status"] != "WAITING_OWNER"
    reply = body["discovery_reply"] or ""
    assert "6/" in reply or "Сроки" in reply

    tz_prep = _drive_discovery_to_owner(client, pid)
    assert tz_prep.json()["project_status"] == "WAITING_OWNER"
    content = client.get(f"/projects/{pid}/artifacts/draft-tz").json()["content"]
    assert "Без оплаты" in content
    assert "личного кабинета" in content


def test_vague_free_text_does_not_advance_topic(client):
    created = client.post("/projects", json={"name": "Vague", "product_type": "website"})
    pid = created.json()["id"]
    first = client.post(f"/projects/{pid}/messages", json={"text": "ну чтоб было удобно"})
    body = first.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert body.get("topic_id") == "purpose_problem"
    assert "конкретнее" in (body["discovery_reply"] or "").lower()


def test_chip_answer_advances_topic(client):
    created = client.post("/projects", json={"name": "Chip", "product_type": "website"})
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Клиентам неудобно оставлять заявки / получать информацию"},
    )
    body = first.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert body.get("topic_id") != "purpose_problem"
    assert "Тип решения" in (body["discovery_reply"] or "") or body.get("topic_id") == "product_shape"


def test_second_vague_answer_escalates_topic(client):
    created = client.post("/projects", json={"name": "EscalateVague", "product_type": "website"})
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/messages", json={"text": "ну чтоб было удобно"})
    second = client.post(f"/projects/{pid}/messages", json={"text": "просто чтобы было хорошо"})
    body = second.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert body.get("topic_id") != "purpose_problem"
    kg = client.post(f"/projects/{pid}/coordinator/discovery")
    assert kg.json()["output"]["coverage"]["open_question_count"] >= 1


def _fill_topics_without_metrics(client, project_id: str):
    last = None
    for _ in range(40):
        last = client.post(
            f"/projects/{project_id}/messages",
            json={"text": "Для пекарни фиксируем этот раздел ТЗ подробно."},
        )
        assert last.status_code == 201
        body = last.json()
        if body.get("discovery_stage") == DiscoveryStage.REVIEW.value:
            return last
        if body["project_status"] == "WAITING_OWNER":
            return last
    raise AssertionError("Did not reach REVIEW")


def test_ready_blocked_when_quality_floor_fails(client):
    created = client.post("/projects", json={"name": "QualityGate", "product_type": "website"})
    pid = created.json()["id"]
    review = _fill_topics_without_metrics(client, pid)
    assert review.json()["project_status"] != "WAITING_OWNER"
    ready = client.post(f"/projects/{pid}/messages", json={"text": "готово"})
    body = ready.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert "качеств" in (body["discovery_reply"] or "").lower() or "рано" in (
        body["discovery_reply"] or ""
    ).lower()


def test_clarify_quota_does_not_ask_sixth(client):
    from discovery.quality import MAX_CLARIFY_QUESTIONS, build_clarify_queue

    queue = build_clarify_queue(requirements=[], open_questions=[])
    assert len(queue) == MAX_CLARIFY_QUESTIONS

    created = client.post("/projects", json={"name": "ClarifyCap", "product_type": "website"})
    pid = created.json()["id"]
    review = _fill_topics_without_metrics(client, pid)
    asked = 0
    last = review
    for _ in range(8):
        body = last.json()
        topic = str(body.get("topic_id") or "")
        if not topic.startswith("clarify:"):
            break
        asked += 1
        last = client.post(f"/projects/{pid}/messages", json={"text": "1"})
        assert last.status_code == 201
    assert asked <= MAX_CLARIFY_QUESTIONS
    leftover = last.json()
    assert not str(leftover.get("topic_id") or "").startswith("clarify:") or asked == MAX_CLARIFY_QUESTIONS
    if asked == MAX_CLARIFY_QUESTIONS:
        kg = client.post(f"/projects/{pid}/coordinator/discovery")
        assert kg.json()["output"]["coverage"]["open_question_count"] >= 1


def test_is_underspecified_unit():
    from discovery.quality import is_underspecified

    assert is_underspecified("ну чтоб было удобно") is True
    assert is_underspecified("Клиентам неудобно оставлять заявки", has_choice=True) is False
    assert (
        is_underspecified(
            "Нужен сайт визитка для пекарни с формой заявки и телефоном."
        )
        is False
    )


def test_recommended_chip_on_safe_defaults():
    from discovery.tz_outline import topic_by_id

    oos = topic_by_id("out_of_scope")
    assert oos is not None
    assert any(c.recommended and c.id == "oos_payments" for c in oos.options)
    purpose = topic_by_id("purpose_problem")
    assert purpose is not None
    assert not any(c.recommended for c in purpose.options)


def test_content_topics_for_bot_and_miniapp():
    from discovery.tz_outline import topics_for

    bot_ids = [topic.id for topic in topics_for("telegram_bot")]
    for topic_id in (
        "delivery_surface",
        "public_identity",
        "offer_catalog",
        "visitor_cta",
        "brand_assets",
        "design_references",
        "design_direction",
    ):
        assert topic_id in bot_ids
    assert "pages_sections" not in bot_ids
    mini_ids = [
        topic.id
        for topic in topics_for("telegram_bot", task_shape="telegram_miniapp")
    ]
    assert "pages_sections" in mini_ids
    site_ids = [topic.id for topic in topics_for("website")]
    assert "public_identity" in site_ids
    assert "promotion" in site_ids
    assert "design_references" in site_ids
    assert "design_direction" in site_ids
    assert "legal_compliance" in site_ids
    assert "delivery_surface" not in site_ids


def test_insufficient_identity_chip_does_not_advance(client):
    created = client.post(
        "/projects", json={"name": "IdentityGate", "product_type": "website"}
    )
    pid = created.json()["id"]
    last = _seek_topic(client, pid, "public_identity")
    assert last.json().get("topic_id") == "public_identity"
    blocked = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Сейчас напишу имя/бренд, роль и слоган"},
    )
    body = blocked.json()
    assert body.get("topic_id") == "public_identity"
    assert "конкретнее" in (body["discovery_reply"] or "").lower()


def test_insufficient_reference_chip_does_not_advance(client):
    created = client.post(
        "/projects", json={"name": "RefGate", "product_type": "website"}
    )
    pid = created.json()["id"]
    last = _seek_topic(client, pid, "design_references")
    assert last.json().get("topic_id") == "design_references"
    blocked = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Сейчас дам ссылки и что в них нравится"},
    )
    body = blocked.json()
    assert body.get("topic_id") == "design_references"
    assert "конкретнее" in (body["discovery_reply"] or "").lower()
    closed = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "Нравится apple.com: много воздуха, крупная типографика, "
                "без кричащих баннеров."
            )
        },
    )
    assert closed.json().get("topic_id") != "design_references"


def test_design_direction_calm_chip_closes(client):
    created = client.post(
        "/projects", json={"name": "LookGate", "product_type": "website"}
    )
    pid = created.json()["id"]
    last = _seek_topic(client, pid, "design_direction")
    assert last.json().get("topic_id") == "design_direction"
    closed = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Спокойный, лаконичный, много воздуха"},
    )
    assert closed.status_code == 201
    assert closed.json().get("topic_id") != "design_direction"


def test_waiting_owner_resumes_missing_content_topics(client):
    import uuid

    from apps.api.main import app
    from core.db import get_db
    from core.models import Project, ProjectStatus
    from discovery.fsm import DiscoveryStage
    from knowledge.repository import KnowledgeRepository

    created = client.post(
        "/projects",
        json={
            "name": "BusinessCard",
            "product_type": "website",
            "customer_telegram_id": "77007",
        },
    )
    pid = created.json()["id"]
    last = _drive_discovery_to_owner(client, pid)
    assert last.json()["project_status"] == "WAITING_OWNER"

    content_ids = {
        "public_identity",
        "offer_catalog",
        "visitor_cta",
        "brand_assets",
        "design_references",
        "design_direction",
        "pages_sections",
    }
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        project = db.get(Project, uuid.UUID(pid))
        assert project is not None
        kg = KnowledgeRepository(db)
        entities = kg.list_entities(project.id, type_="Project")
        state = dict(entities[0].payload or {})
        state["answered_topics"] = [
            tid
            for tid in (state.get("answered_topics") or [])
            if tid not in content_ids
        ]
        state["discovery_stage"] = DiscoveryStage.READY_FOR_OWNER.value
        state["owner_draft_emitted"] = True
        kg.update_entity(entities[0], payload=state)
        project.status = ProjectStatus.WAITING_OWNER
        db.commit()
    finally:
        db.close()

    ws = client.get(
        f"/projects/{pid}/workspace",
        params={"customer_telegram_id": "77007", "mode": "create"},
    )
    assert ws.status_code == 200
    data = ws.json()
    assert data["status"] == "WAITING_CUSTOMER"
    reply = " ".join(m["text"] for m in data["messages"][-3:])
    assert any(
        marker in reply
        for marker in (
            "Страницы и CTA",
            "Имя и подпись",
            "Услуги и портфолио",
            "Как посетитель связывается",
            "Референсы",
            "Какой дизайн хотите",
        )
    )


def test_miniapp_shape_sets_task_and_pages(client):
    created = client.post("/projects", json={"name": "MiniShape"})
    pid = created.json()["id"]
    client.post(
        f"/projects/{pid}/messages",
        json={"text": "Нужно автоматизировать заявки"},
    )
    shaped = client.post(
        f"/projects/{pid}/messages",
        json={"text": "3. Telegram Mini App / лендинг в Telegram"},
    )
    assert shaped.status_code == 201
    project = client.get(f"/projects/{pid}").json()
    assert project["product_type"] == "telegram_bot"
    last = _seek_topic(client, pid, "pages_sections", limit=25, start=shaped)
    assert last.json().get("topic_id") == "pages_sections"


def _reach_closing(client, project_id: str):
    last = None
    for i in range(90):
        if last is not None:
            body = last.json()
            topic = str(body.get("topic_id") or "")
            if topic.startswith("closing:"):
                return last
            if topic.startswith("clarify:"):
                last = client.post(
                    f"/projects/{project_id}/messages",
                    json={"text": "1"},
                )
                assert last.status_code == 201
                continue
            if body["project_status"] == "WAITING_OWNER":
                raise AssertionError("Reached WAITING_OWNER before closing wrap-up")
        topic = last.json().get("topic_id") if last is not None else None
        last = client.post(
            f"/projects/{project_id}/messages",
            json={"text": _content_reply_for_topic(topic, i)},
        )
        assert last.status_code == 201
    raise AssertionError("Did not reach closing wrap-up")


def test_closing_wrapup_adds_notes_budget_and_download(client):
    created = client.post(
        "/projects",
        json={
            "name": "WrapUp",
            "product_type": "website",
            "customer_telegram_id": "55001",
        },
    )
    pid = created.json()["id"]
    first = _reach_closing(client, pid)
    assert first.json().get("topic_id") == "closing:closing_additions"

    added = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Ещё нужна тёмная тема и кнопка «Позвонить» на главной."},
    )
    assert added.json().get("topic_id") == "closing:closing_budget"
    assert added.json()["project_status"] != "WAITING_OWNER"

    budget = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Закладываю 120 тысяч рублей на MVP с хостингом."},
    )
    assert budget.json().get("topic_id") == "closing:closing_brief"

    skip_brief = client.post(f"/projects/{pid}/messages", json={"text": "1"})
    assert skip_brief.status_code == 201
    ready = skip_brief
    if ready.json()["project_status"] != "WAITING_OWNER":
        ready = client.post(f"/projects/{pid}/messages", json={"text": "готово"})
    body = ready.json()
    assert body["project_status"] == "WAITING_OWNER"
    assert body.get("tz_available") is True
    assert "скач" in (body["discovery_reply"] or "").lower()

    tz = client.get(f"/projects/{pid}/artifacts/draft-tz").json()["content"]
    assert "тёмная тема" in tz
    assert "120 тысяч" in tz

    exported = client.get(
        f"/projects/{pid}/tz-export",
        params={"format": "md", "customer_telegram_id": "55001"},
    )
    assert exported.status_code == 200
    assert "тёмная тема" in exported.text
    assert "120 тысяч" in exported.text


def test_closing_brief_file_lands_in_tz(client):
    created = client.post(
        "/projects",
        json={
            "name": "BriefFile",
            "product_type": "website",
            "customer_telegram_id": "55002",
        },
    )
    pid = created.json()["id"]
    _reach_closing(client, pid)
    additions_done = client.post(f"/projects/{pid}/messages", json={"text": "1"})
    assert additions_done.json().get("topic_id") == "closing:closing_budget"
    budget_done = client.post(f"/projects/{pid}/messages", json={"text": "1"})
    assert budget_done.json().get("topic_id") == "closing:closing_brief"

    content = (
        "# Постановка из ChatGPT\n\nНужен лендинг пекарни с формой заявки и фото витрины."
    ).encode("utf-8")
    attached = client.post(
        f"/projects/{pid}/messages/file",
        params={"customer_telegram_id": "55002"},
        files={"file": ("chatgpt-brief.md", io.BytesIO(content), "text/markdown")},
    )
    assert attached.status_code == 201
    if attached.json()["project_status"] != "WAITING_OWNER":
        attached = client.post(f"/projects/{pid}/messages", json={"text": "готово"})
    assert attached.json()["project_status"] == "WAITING_OWNER"
    tz = client.get(f"/projects/{pid}/artifacts/draft-tz").json()["content"]
    assert "лендинг пекарни" in tz
    assert "chatgpt-brief.md" in tz or "Source brief" in tz


def test_extract_docx_brief_text():
    import io

    from docx import Document

    from core.project_files import extract_attachment_text

    doc = Document()
    doc.add_paragraph("Постановка: бот записи в салон с напоминаниями.")
    buf = io.BytesIO()
    doc.save(buf)
    text = extract_attachment_text(
        buf.getvalue(),
        "brief.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert "бот записи" in text


def test_heuristic_outline_skips_landing_for_internal_bot():
    from discovery.adapt import heuristic_plan
    from discovery.tz_outline import remaining_topics

    plan = heuristic_plan(
        product_type="telegram_bot",
        task_shape="telegram_bot",
        texts=["Need a Telegram bot for salon booking with reminders. Users pick a time slot."],
    )
    ids = [
        topic.id
        for topic in remaining_topics(
            "telegram_bot",
            task_shape="telegram_bot",
            done_ids=set(),
            plan=plan,
        )
    ]
    assert "booking_rules" in ids
    assert "notification_rules" in ids
    assert "offer_catalog" not in ids
    assert "public_identity" not in ids
    assert "promotion" not in ids
    assert "design_references" not in ids
    assert "design_direction" not in ids
    assert "legal_compliance" in ids
    assert "purpose_problem" in ids
    assert "budget" in ids


def test_website_keeps_public_presence_modules():
    from discovery.adapt import heuristic_plan
    from discovery.tz_outline import remaining_topics

    plan = heuristic_plan(
        product_type="website",
        task_shape=None,
        texts=["Нужен сайт-визитка для пекарни с формой заявки."],
    )
    ids = [
        topic.id
        for topic in remaining_topics(
            "website", task_shape=None, done_ids=set(), plan=plan
        )
    ]
    assert "public_identity" in ids
    assert "offer_catalog" in ids
    assert "promotion" in ids
    assert "design_references" in ids
    assert "design_direction" in ids
    assert "legal_compliance" in ids
    assert "booking_rules" not in ids


def test_heuristic_rewrites_questions_and_option_chips():
    from discovery.adapt import heuristic_plan
    from discovery.literacy import ITLiteracy
    from discovery.questions import build_prompt
    from discovery.tz_outline import remaining_topics

    idea = "Нужен Telegram-бот записи в салон красоты с напоминаниями о визите."
    plan = heuristic_plan(
        product_type="telegram_bot",
        task_shape="telegram_bot",
        texts=[idea],
    )
    assert plan.task_brief
    assert "салон" in plan.task_brief.lower() or "запис" in plan.task_brief.lower()
    assert "must_features" in plan.question_overrides
    assert "слот" in plan.question_overrides["must_features"].lower() or "запис" in (
        plan.question_overrides["must_features"].lower()
    )
    assert plan.option_overrides["must_features"]["feat_intake"]
    assert "слот" in plan.option_overrides["must_features"]["feat_intake"].lower()
    assert plan.title_overrides["must_features"] == "Функции записи"
    ids = [
        topic.id
        for topic in remaining_topics(
            "telegram_bot",
            task_shape="telegram_bot",
            done_ids=set(),
            plan=plan,
        )
    ]
    assert "custom:who_books" in ids
    assert "booking_rules" in ids

    prompt = build_prompt(
        stage=DiscoveryStage.FUNCTIONAL,
        literacy=ITLiteracy.LOW,
        product_type="telegram_bot",
        task_shape="telegram_bot",
        topic_id="must_features",
        done_ids={"purpose_problem", "product_shape"},
        plan=plan,
        announce_outline=True,
    )
    blob = prompt.text.lower()
    assert "функции записи" in blob
    assert "салон" in blob or "запис" in blob
    assert "не спрашиваю" in blob
    assert "выберите вариант:" not in blob
    assert not any(ln.strip().startswith("1. ") for ln in prompt.text.splitlines())
    labels = [c.label.lower() for c in prompt.choices]
    assert any("слот" in label or "запис" in label for label in labels)


def test_described_task_rewrites_next_question_and_chips(client):
    created = client.post("/projects", json={"name": "чвап"})
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "Нужен Telegram-бот записи в салон красоты с напоминаниями "
                "клиенту о визите. Клиент сам выбирает слот."
            )
        },
    )
    assert first.status_code == 201
    reply = (first.json().get("discovery_reply") or "").lower()
    assert first.json().get("topic_id") == "product_shape"
    assert "вы описали" in reply or "по задаче" in reply
    assert "салон" in reply or "запис" in reply
    assert "добавляю" in reply
    assert "не спрашиваю" in reply
    labels = " ".join(
        str(c.get("label") or "") for c in first.json().get("discovery_choices") or []
    ).lower()
    assert "бот" in labels
    assert "записи" in labels or "слот" in labels or "как вы описали" in labels
    recommended = [
        c for c in first.json().get("discovery_choices") or [] if c.get("recommended")
    ]
    assert recommended
    assert recommended[0]["id"] == "shape_bot"

    second = client.post(
        f"/projects/{pid}/messages",
        json={"text": "2. Telegram-бот"},
    )
    assert second.status_code == 201
    body = (second.json().get("discovery_reply") or "").lower()
    assert "как сейчас" in body or "запис" in body
    assert "салон" in body or "бот" in body


def test_previous_answers_ground_next_choice_chips():
    from discovery.adapt import heuristic_plan
    from discovery.literacy import ITLiteracy
    from discovery.questions import build_prompt
    from discovery.rephrase import apply_choice_overrides, extract_mentioned_tools
    from discovery.tz_outline import topic_by_id

    idea = (
        "Нужен Telegram-бот записи в салон красоты. "
        "Сейчас записываем в WhatsApp и в тетрадку."
    )
    tools = extract_mentioned_tools([idea])
    assert any(slug == "whatsapp" for slug, _ in tools)
    assert any(slug == "notebook" for slug, _ in tools)
    assert not any(slug == "telegram" for slug, _ in tools)

    plan = heuristic_plan(
        product_type="telegram_bot",
        task_shape="telegram_bot",
        texts=[idea],
        previous_answers={"purpose_problem": idea},
    )
    asis = topic_by_id("as_is_process")
    assert asis is not None
    labels = [c.label.lower() for c in apply_choice_overrides(asis, plan)]
    blob = " ".join(labels)
    assert "whatsapp" in blob
    assert "тетрад" in blob
    assert any(c.id.startswith("ctx:") for c in apply_choice_overrides(asis, plan))
    hidden_shape = plan.hidden_option_ids.get("product_shape") or ()
    assert "shape_api" in hidden_shape
    assert "shape_website" not in hidden_shape
    assert "shape_bot" not in hidden_shape

    prompt = build_prompt(
        stage=DiscoveryStage.UNDERSTANDING_IDEA,
        literacy=ITLiteracy.LOW,
        product_type="telegram_bot",
        task_shape="telegram_bot",
        topic_id="as_is_process",
        done_ids={"purpose_problem", "product_shape"},
        plan=plan,
    )
    choice_blob = " ".join(c.label.lower() for c in prompt.choices)
    assert "whatsapp" in choice_blob


def test_llm_adds_contextual_choice_chips_from_previous_answers():
    from discovery.adapt import adapt_outline, adapt_topic_choices, heuristic_plan
    from discovery.rephrase import apply_choice_overrides
    from discovery.tz_outline import topic_by_id

    idea = "Бот записи. Сейчас клиенты пишут в WhatsApp."
    heuristic = heuristic_plan(
        product_type="telegram_bot",
        task_shape="telegram_bot",
        texts=[idea],
        previous_answers={"purpose_problem": idea},
    )

    def fake_outline(_system: str, _user: str) -> dict:
        return {
            "option_overrides": {
                "as_is_process": {
                    "asis_chat": "Как вы сказали: запись сейчас идёт в WhatsApp",
                }
            },
            "extra_options": {
                "as_is_process": [
                    {
                        "id": "ctx:keep_whatsapp",
                        "label": "WhatsApp остаётся, бот только напоминает",
                    }
                ]
            },
        }

    plan = adapt_outline(
        product_type="telegram_bot",
        task_shape="telegram_bot",
        texts=[idea],
        previous_answers={"purpose_problem": idea},
        llm_json=fake_outline,
    )
    asis = topic_by_id("as_is_process", plan.extra_topics)
    assert asis is not None
    labels = {c.id: c.label for c in apply_choice_overrides(asis, plan)}
    assert "whatsapp" in labels["asis_chat"].lower()
    assert "ctx:keep_whatsapp" in labels

    def fake_next(_system: str, _user: str) -> dict:
        return {
            "option_overrides": {
                "asis_sheets": "Тетрадку не ведём — только WhatsApp",
            },
            "extra_options": [
                {"id": "ctx:wa_admin", "label": "Админ переносит заявки из WhatsApp"}
            ],
            "recommended_option_id": "asis_chat",
        }

    plan = adapt_topic_choices(
        topic=asis,
        plan=plan,
        previous_answers={"purpose_problem": idea},
        llm_json=fake_next,
    )
    labels = {c.id: c.label for c in apply_choice_overrides(asis, plan)}
    assert "тетрад" in labels["asis_sheets"].lower() or "whatsapp" in labels["asis_sheets"].lower()
    assert "ctx:wa_admin" in labels


def test_described_task_chips_follow_previous_answers(client):
    created = client.post("/projects", json={"name": "SalonWA"})
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "Нужен Telegram-бот записи в салон красоты. "
                "Сейчас записываем в WhatsApp и в тетрадку."
            )
        },
    )
    assert first.status_code == 201
    assert first.json().get("topic_id") == "product_shape"
    shape_ids = [c.get("id") for c in first.json().get("discovery_choices") or []]
    assert "shape_bot" in shape_ids
    assert "shape_api" not in shape_ids
    assert "shape_website" in shape_ids

    second = client.post(
        f"/projects/{pid}/messages",
        json={"text": "2. Telegram-бот"},
    )
    assert second.status_code == 201
    assert second.json().get("topic_id") == "as_is_process"
    asis_labels = " ".join(
        str(c.get("label") or "") for c in second.json().get("discovery_choices") or []
    ).lower()
    assert "whatsapp" in asis_labels
    assert "тетрад" in asis_labels


def test_android_idea_puts_android_and_ios_on_solution_type(client):
    from discovery.rephrase import extract_requested_surfaces

    assert any(slug == "android" for slug, _ in extract_requested_surfaces(
        ["Нужно создать приложение для Android с каталогом товаров."]
    ))

    created = client.post("/projects", json={"name": "AndroidApp"})
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "Нужно создать приложение для Android с каталогом товаров "
                "и корзиной для клиентов."
            )
        },
    )
    assert first.status_code == 201
    assert first.json().get("topic_id") == "product_shape"
    choices = first.json().get("discovery_choices") or []
    ids = [c.get("id") for c in choices]
    labels = [str(c.get("label") or "").lower() for c in choices]
    blob = " ".join(labels)
    assert ids[0] == "ctx:shape_android"
    assert "ctx:shape_ios" in ids
    assert "android" in blob
    assert "ios" in blob
    recommended = [c for c in choices if c.get("recommended")]
    assert recommended
    assert recommended[0]["id"] == "ctx:shape_android"
    reply = (first.json().get("discovery_reply") or "").lower()
    assert "android" in reply


def test_llm_cannot_skip_core_topics():
    from discovery.adapt import heuristic_plan, sanitize_llm_proposal

    heuristic = heuristic_plan(
        product_type="website",
        task_shape=None,
        texts=["Landing for a studio"],
    )
    plan = sanitize_llm_proposal(
        {
            "skip_topic_ids": ["purpose_problem", "budget", "legal_compliance", "offer_catalog"],
            "extra_topics": [
                {
                    "id": "custom:portfolio_layout",
                    "stage": "FUNCTIONAL",
                    "parent_id": "offer_catalog",
                    "title_ru": "Как показать портфолио",
                    "title_en": "Portfolio layout",
                    "question_ru": "Сетка кейсов или список ссылок в первой версии?",
                    "options": [
                        {"id": "grid", "label": "Сетка из 3–6 кейсов"},
                        {"id": "links", "label": "Список ссылок"},
                    ],
                    "why": "Studio landing needs portfolio presentation",
                }
            ],
        },
        heuristic=heuristic,
        locked_ids=set(),
    )
    assert "purpose_problem" not in plan.skipped_ids
    assert "budget" not in plan.skipped_ids
    assert "legal_compliance" not in plan.skipped_ids
    assert any(t.id == "custom:portfolio_layout" for t in plan.extra_topics)


def test_booking_bot_interview_asks_booking_not_catalog(client):
    created = client.post(
        "/projects", json={"name": "SalonBot", "product_type": "telegram_bot"}
    )
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "Need a Telegram bot for salon booking with reminders. "
                "Users pick a time slot."
            )
        },
    )
    assert first.status_code == 201
    client.post(
        f"/projects/{pid}/messages",
        json={"text": "2. Telegram-бот"},
    )
    seen: list[str] = []
    last = None
    for i in range(45):
        last = client.post(
            f"/projects/{pid}/messages",
            json={
                "text": (
                    f"Достаточно деталей для раздела MVP номер {i + 1}: "
                    "фиксируем ответ заказчика для первой версии. "
                    "Запись на слот и напоминание клиенту."
                )
            },
        )
        assert last.status_code == 201
        tid = str(last.json().get("topic_id") or "")
        seen.append(tid)
        if last.json().get("discovery_stage") == DiscoveryStage.REVIEW.value:
            break
    assert "booking_rules" in seen
    assert "offer_catalog" not in seen
    assert "public_identity" not in seen
    assert "promotion" not in seen
    assert "design_references" not in seen
    assert "design_direction" not in seen
    assert "legal_compliance" in seen


def test_infer_does_not_auto_close_content_topics():
    from discovery.adapt import heuristic_plan, infer_already_answered
    from discovery.tz_outline import remaining_topics

    idea = (
        "Миниапп Телеграм, визитка студии Uni4It: сайты, лендинги, telegram боты, "
        "AI автоматизация. Дизайн с вау эффектами, 3D визуализация и анимация."
    )
    plan = heuristic_plan(
        product_type="telegram_bot",
        task_shape="telegram_miniapp",
        texts=[idea],
    )
    leftover = {
        topic.id
        for topic in remaining_topics(
            "telegram_bot",
            task_shape="telegram_miniapp",
            done_ids=set(),
            plan=plan,
        )
    }
    found = infer_already_answered(plan, corpus=idea, leftover_ids=leftover)
    assert "visitor_cta" not in found
    assert "design_direction" not in found
    assert "public_identity" not in found
    assert "offer_catalog" not in found
    assert "design_references" not in found


def test_substance_gates_implementation_content():
    from discovery.substance import should_reask
    from discovery.tz_outline import topic_by_id

    refs = topic_by_id("design_references")
    catalog = topic_by_id("offer_catalog")
    cta = topic_by_id("visitor_cta")
    identity = topic_by_id("public_identity")
    integ = topic_by_id("integrations")
    ops = topic_by_id("ops_constraints")
    assert refs and catalog and cta and identity and integ and ops

    assert should_reask(
        refs, [], "https://novikova.duckdns.org/\nhttps://example.com/", 
        "https://novikova.duckdns.org/\nhttps://example.com/",
    )
    assert should_reask(refs, [], "https://apple.com/ : много воздуха, крупная типографика", 
        "https://apple.com/ : много воздуха, крупная типографика") is None

    sites = next(c for c in catalog.options if c.id == "cat_sites")
    bots = next(c for c in catalog.options if c.id == "cat_bots")
    portfolio = next(c for c in catalog.options if c.id == "cat_portfolio")
    stub = next(c for c in catalog.options if c.id == "cat_stub")
    assert should_reask(catalog, [sites, bots, portfolio], "", "Сайты и лендинги; Telegram-боты")
    assert should_reask(catalog, [sites, stub], "", stub.label) is None

    form = next(c for c in cta.options if c.id == "cta_form")
    assert should_reask(cta, [form], "", form.label) is None
    assert should_reask(
        cta, [], "Заявки уходят в телеграм-канал.", "Заявки уходят в телеграм-канал."
    )
    assert should_reask(
        cta, [], "Заявки в канал @uni4it_leads", "Заявки в канал @uni4it_leads"
    ) is None

    assert should_reask(identity, [], "Бренд студии UNI4IT", "Бренд студии UNI4IT") is None
    chip = next(c for c in identity.options if c.id == "id_write")
    assert should_reask(identity, [chip], "", chip.label)

    existing = next(c for c in ops.options if c.id == "ops_existing")
    simple = next(c for c in ops.options if c.id == "ops_simple")
    assert should_reask(ops, [simple, existing], "", f"{simple.label}; {existing.label}")
    assert should_reask(
        ops,
        [simple, existing],
        "asf.example.com",
        f"{simple.label}; {existing.label}. asf.example.com",
    ) is None

    assert should_reask(
        integ, [], "Заявки уходят в телеграм-канал.", "Заявки уходят в телеграм-канал."
    )
    this_chat = next(c for c in integ.options if c.id == "int_this_chat")
    assert should_reask(integ, [this_chat], "", this_chat.label) is None


def test_wow_idea_still_asks_cta_and_design(client):
    created = client.post(
        "/projects",
        json={"name": "Card", "product_type": "telegram_bot"},
    )
    pid = created.json()["id"]
    first = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "Миниапп Телеграм, визитка студии Uni4It: сайты, лендинги, боты. "
                "Нужна 3D визуализация и анимация с вау эффектами."
            )
        },
    )
    assert first.status_code == 201
    last = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Telegram Mini App / лендинг в Telegram"},
    )
    seen: list[str] = [str(last.json().get("topic_id") or "")]
    for i in range(40):
        current = last.json().get("topic_id") if last is not None else None
        last = client.post(
            f"/projects/{pid}/messages",
            json={"text": _content_reply_for_topic(current, i)},
        )
        assert last.status_code == 201
        tid = str(last.json().get("topic_id") or "")
        seen.append(tid)
        if last.json().get("discovery_stage") == DiscoveryStage.REVIEW.value:
            break
    assert "visitor_cta" in seen
    assert "design_direction" in seen
    assert "design_references" in seen


def test_bare_reference_urls_do_not_close(client):
    created = client.post(
        "/projects", json={"name": "RefUrls", "product_type": "website"}
    )
    pid = created.json()["id"]
    last = _seek_topic(client, pid, "design_references")
    blocked = client.post(
        f"/projects/{pid}/messages",
        json={
            "text": (
                "https://novikova.duckdns.org/\n"
                "https://annamurdesign.duckdns.org/"
            )
        },
    )
    assert blocked.json().get("topic_id") == "design_references"
    assert "конкретнее" in (blocked.json()["discovery_reply"] or "").lower()


def test_discuss_with_developer_still_escalates(client):
    created = client.post(
        "/projects", json={"name": "PromoHandOff", "product_type": "website"}
    )
    pid = created.json()["id"]
    last = _seek_topic(client, pid, "promotion")
    assert last.json().get("topic_id") == "promotion"
    handed = client.post(
        f"/projects/{pid}/messages",
        json={"text": "Обсудить с разработчиком, что нужно зафиксировать"},
    )
    assert handed.status_code == 201
    assert handed.json().get("topic_id") != "promotion"


def test_discovery_progress_recomputes_when_total_grows():
    from core.models import Project, ProjectStatus
    from discovery.progress import compute_discovery_progress

    project = Project(
        name="Bar",
        status=ProjectStatus.WAITING_CUSTOMER,
        product_type=None,
    )
    empty = compute_discovery_progress(project, {"answered_topics": []})
    project.product_type = "telegram_bot"
    grown = compute_discovery_progress(
        project,
        {
            "task_shape": "telegram_miniapp",
            "outline_adapted": True,
            "capabilities": ["public_presence", "leads", "catalog"],
            "answered_topics": ["purpose_problem", "product_shape"],
            "escalated_topics": [],
        },
    )
    assert grown["total"] > empty["total"]
    assert grown["done"] == 2
    assert grown["remaining"] == grown["total"] - 2
    assert 0 < grown["ratio"] < 1

    project.status = ProjectStatus.WAITING_OWNER
    done = compute_discovery_progress(
        project,
        {
            "task_shape": "telegram_miniapp",
            "outline_adapted": True,
            "capabilities": ["public_presence", "leads"],
            "answered_topics": ["purpose_problem"],
            "discovery_stage": "READY_FOR_OWNER",
        },
    )
    assert done["phase"] == "done"
    assert done["done"] == done["total"]
    assert done["percent"] == 100
    assert done["remaining"] == 0
