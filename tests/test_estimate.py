"""Delivery-cost heuristic and owner notify when a draft TZ is ready."""

from __future__ import annotations

from types import SimpleNamespace

from core.config import get_settings
from core.estimate import (
    SIMPLE_MVP_HOUR_CAP,
    estimate_delivery,
    format_estimate_review_block,
    format_owner_draft_ready_message,
)
from tests.test_discovery import _drive_discovery_to_owner


def _req(priority: str = "should", status: str = "new"):
    return SimpleNamespace(status=status, payload={"priority": priority})


def _q(status: str = "open"):
    return SimpleNamespace(status=status, payload={"question": "gap"})


def _risk(status: str = "active"):
    return SimpleNamespace(status=status, payload={"description": "risk"})


def test_base_hours_by_product_type():
    for product, base in (
        ("website", 16),
        ("telegram_bot", 20),
        ("rest_service", 24),
        ("ai_automation", 24),
        ("mobile_native", 32),
        (None, 20),
        ("unknown", 20),
    ):
        est = estimate_delivery(
            product_type=product,
            hourly_rate=3000,
            currency="RUB",
        )
        assert est.hours == base
        assert est.cost == round(base * 3000)
        assert est.currency == "RUB"
        assert est.capped is False


def test_requirement_priority_hours_and_skips():
    est = estimate_delivery(
        product_type="website",
        requirements=[
            _req("must"),
            _req("P1"),
            _req("should"),
            _req("could"),
            _req("must", status="superseded"),
            _req("must", status="archived"),
            _req("must", status="rejected"),
            _req("wont"),
        ],
        hourly_rate=3000,
        currency="RUB",
    )
    # 16 + 2 must/P1 * 2 + 1 should + 0.5 could = 21.5
    assert est.must_count == 2
    assert est.should_count == 1
    assert est.could_count == 1
    assert est.skipped_requirement_count == 4
    assert est.hours == 21.5
    assert est.cost == round(21.5 * 3000)


def test_open_questions_and_risks_add_hours():
    est = estimate_delivery(
        product_type="telegram_bot",
        open_questions=[_q("open"), _q("active"), _q("resolved")],
        risks=[_risk("active"), _risk("rejected")],
        hourly_rate=3000,
        currency="RUB",
    )
    # 20 + 2 open * 2 + 1 risk * 3 = 27
    assert est.open_question_count == 2
    assert est.risk_count == 1
    assert est.hours == 27
    assert est.cost == 27 * 3000


def test_simple_mvp_hour_cap():
    many_musts = [_req("must") for _ in range(40)]
    est = estimate_delivery(
        product_type="website",
        requirements=many_musts,
        hourly_rate=3000,
        currency="RUB",
    )
    assert est.hours_uncapped == 16 + 40 * 2
    assert est.hours == SIMPLE_MVP_HOUR_CAP
    assert est.capped is True
    assert est.cost == round(SIMPLE_MVP_HOUR_CAP * 3000)
    assert any("Потолок" in line for line in est.rationale)
    assert 4 <= len(est.rationale) <= 8


def test_owner_message_includes_cost_and_review_command():
    est = estimate_delivery(
        product_type="website",
        requirements=[_req("must")],
        hourly_rate=3000,
        currency="RUB",
    )
    pid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    text = format_owner_draft_ready_message(
        name="Пекарня",
        project_id=pid,
        estimate=est,
    )
    assert "Пекарня" in text
    assert pid in text
    assert "RUB" in text
    assert "ч" in text
    assert "/review" in text
    assert pid in text.split("/review", 1)[1]
    assert "Почему так" in text
    assert "оценка для владельца" in text.lower()
    assert "HITL" in text
    review = format_estimate_review_block(est)
    assert review
    assert "Оценка" in review


def _budget(description: str):
    return SimpleNamespace(
        status="new",
        payload={
            "topic_id": "budget",
            "description": description,
            "priority": "should",
        },
    )


def test_customer_budget_chip_is_context_not_quote():
    est = estimate_delivery(
        product_type="website",
        requirements=[_req("must"), _req("must"), _budget("Есть ориентир до ~50 тыс. ₽")],
        hourly_rate=3000,
        currency="RUB",
    )
    # 16 + 4 must + 1 should(budget) = 21h → 63 000, above 50k chip
    assert est.hours == 21
    assert est.cost == 63_000
    assert est.cost != 50_000
    assert est.budget_fit == "above"
    assert "50" in est.customer_budget_label
    assert any("ВЫШЕ" in line for line in est.rationale)


def test_customer_budget_mid_range_and_quote_request():
    mid = estimate_delivery(
        product_type="website",
        requirements=[_budget("Ориентир примерно 50–200 тыс. ₽")],
        hourly_rate=3000,
        currency="RUB",
    )
    assert mid.budget_fit == "within"
    assert mid.customer_budget_min == 50_000
    assert mid.customer_budget_max == 200_000

    asked = estimate_delivery(
        product_type="website",
        requirements=[
            _budget("Сумму не фиксирую — сначала оценка от разработчика")
        ],
        hourly_rate=3000,
        currency="RUB",
    )
    assert asked.budget_fit == "quote_requested"
    assert "не котировка" in " ".join(asked.rationale) or "просит оценку" in asked.customer_budget_label


def test_customer_typed_figure_overrides_chip_numbers():
    est = estimate_delivery(
        product_type="website",
        requirements=[_budget("Сейчас напишу сумму. 80 тыс ₽")],
        hourly_rate=3000,
        currency="RUB",
    )
    assert est.customer_budget_min == 80_000
    assert est.budget_fit == "below"  # 16h+1 should = 17h * 3000 = 51 000
    assert est.cost == 51_000


def test_draft_tz_persists_estimate_and_notifies_owner(client, monkeypatch):
    sent: list[str] = []

    def fake_send(text: str, *, parse_mode: str | None = "Markdown") -> bool:
        sent.append(text)
        return True

    monkeypatch.setenv("OWNER_TELEGRAM_ID", "4242")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ASF_ESTIMATE_HOURLY_RATE", "3000")
    monkeypatch.setenv("ASF_ESTIMATE_CURRENCY", "RUB")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "integrations.telegram.notify.send_owner_telegram",
        fake_send,
    )

    created = client.post(
        "/projects", json={"name": "Bakery Site", "product_type": "website"}
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"

    assert sent, "owner Telegram notify must be attempted when TZ is ready"
    body = sent[-1]
    assert "Bakery Site" in body
    assert project_id in body
    assert "/review" in body
    assert "RUB" in body
    assert "Почему так" in body

    review = client.get(f"/projects/{project_id}/hitl/review")
    assert review.status_code == 200
    estimate = review.json().get("estimate")
    assert estimate
    assert estimate["currency"] == "RUB"
    assert estimate["hourly_rate"] == 3000
    assert estimate["hours"] > 0
    assert estimate["cost"] == round(estimate["hours"] * 3000)
    assert estimate["rationale"]

    tz = client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.status_code == 200
    assert tz.json()["estimate"]["cost"] == estimate["cost"]

    before = len(sent)
    client.post(
        f"/projects/{project_id}/messages",
        json={"text": "Дополнение: форма заявки на главной"},
    )
    assert len(sent) == before

    get_settings.cache_clear()


def test_tz_send_posts_document_to_customer_chat(client, monkeypatch):
    delivered: list[tuple] = []

    def fake_doc(chat_id, *, data, filename, caption=None):
        delivered.append((chat_id, filename, caption, len(data or b"")))
        return True

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "integrations.telegram.notify.send_customer_telegram_document",
        fake_doc,
    )

    created = client.post(
        "/projects",
        json={
            "name": "Send TZ",
            "product_type": "website",
            "customer_telegram_id": "88001",
        },
    )
    project_id = created.json()["id"]
    too_soon = client.post(
        f"/projects/{project_id}/tz-send",
        params={"format": "md", "customer_telegram_id": "88001"},
    )
    assert too_soon.status_code == 409

    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"

    sent = client.post(
        f"/projects/{project_id}/tz-send",
        params={"format": "md", "customer_telegram_id": "88001"},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["sent"] is True
    assert body["filename"]
    assert delivered
    assert delivered[-1][0] == "88001"
    assert delivered[-1][3] > 0
    assert "Черновик ТЗ" in (delivered[-1][2] or "")

    hitl = client.post(f"/projects/{project_id}/hitl", json={"action": "approve"})
    assert hitl.status_code == 200
    again = client.post(
        f"/projects/{project_id}/tz-send",
        params={"format": "md", "customer_telegram_id": "88001"},
    )
    assert again.status_code == 200
    assert again.json()["sent"] is True
    assert "актуальная версия" in (delivered[-1][2] or "")

    get_settings.cache_clear()


def test_tz_send_without_chat_id_explains_fallback(client, monkeypatch):
    import uuid

    from apps.api.main import app
    from core.db import get_db
    from core.models import Project

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()

    created = client.post(
        "/projects",
        json={
            "name": "No Chat",
            "product_type": "website",
            "customer_telegram_id": "88009",
        },
    )
    project_id = created.json()["id"]
    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        row = db.get(Project, uuid.UUID(project_id))
        assert row is not None
        row.customer_telegram_id = None
        db.commit()
    finally:
        db.close()

    sent = client.post(
        f"/projects/{project_id}/tz-send",
        params={"format": "md"},
    )
    assert sent.status_code == 409
    assert "chat_id" in sent.json()["detail"]
    get_settings.cache_clear()
