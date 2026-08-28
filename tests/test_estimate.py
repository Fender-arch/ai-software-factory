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
    assert format_estimate_review_block(est)
    assert "Оценка:" in format_estimate_review_block(est)


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
