"""Client market estimate (DEC-012): calculation, payload, confirm flow."""

from __future__ import annotations

from types import SimpleNamespace

from core.client_estimate import (
    METHOD,
    REPORT_LLM_METHOD,
    REPORT_TEMPLATE_METHOD,
    collect_work_items,
    compose_client_estimate_markdown,
    estimate_client_delivery,
    render_template_report,
    write_client_estimate_report,
)
from core.estimate import estimate_delivery
from core.market_rates import (
    DISCLAIMER_RU,
    _host_allowlisted,
    builtin_market_table,
    load_market_table,
)
from tests.test_discovery import _drive_discovery_to_owner


def _req(priority: str = "must", status: str = "new", name: str = "Req"):
    return SimpleNamespace(
        id="r1",
        name=name,
        status=status,
        payload={"priority": priority},
    )


def _budget(description: str):
    return SimpleNamespace(
        status="new",
        name="Budget",
        payload={
            "topic_id": "budget",
            "description": description,
            "priority": "should",
        },
    )


def test_client_hours_follow_mvp_must_have_package():
    est = estimate_client_delivery(
        product_type="website",
        requirements=[
            _req("must", name="Форма заявки"),
            _req("must", name="Каталог"),
            _req("should", name="Блог"),
            _req("could", name="Анимация"),
            _req("must", status="rejected", name="Старое"),
        ],
        fetch_market=False,
    )
    # 16 base + 2 must * 2 + 1 should * 1 = 21; could is listed but not quoted
    assert est.hours == 21
    assert est.must_count == 2
    assert est.should_count == 1
    assert est.could_count == 1
    assert est.skipped_requirement_count == 1
    assert est.method == METHOD
    assert est.disclaimer == DISCLAIMER_RU
    quoted = [item["name"] for item in est.work_items if item["in_mvp"]]
    assert "Форма заявки" in quoted
    assert "Анимация" not in quoted
    out = [item["name"] for item in est.work_items if not item["in_mvp"]]
    assert "Анимация" in out


def test_client_cost_uses_market_band_not_owner_rate():
    owner = estimate_delivery(
        product_type="website",
        requirements=[_req("must"), _req("must")],
        hourly_rate=3000,
        currency="RUB",
    )
    client = estimate_client_delivery(
        product_type="website",
        requirements=[_req("must"), _req("must")],
        fetch_market=False,
    )
    table = builtin_market_table()
    mid = table["bands"]["ru_cis_freelance"]["hourly"]["mid"]
    low = table["bands"]["ru_cis_freelance"]["hourly"]["low"]
    high = table["bands"]["ru_cis_freelance"]["hourly"]["high"]
    assert client.hourly_rate_mid == mid
    assert client.cost == round(client.hours * mid)
    assert client.cost_low == round(client.hours * low)
    assert client.cost_high == round(client.hours * high)
    assert client.cost != owner.cost
    assert client.currency == "RUB"
    names = " ".join(src["name"] for src in client.sources)
    notes = " ".join(src.get("note") or "" for src in client.sources)
    assert "Admin analytics" not in names
    assert "Admin analytics" not in notes
    assert any(src["kind"] == "config" for src in client.sources)
    assert client.ee_comparison
    assert client.ee_comparison["currency"] == "USD"


def test_client_budget_comparison_and_template_report():
    est = estimate_client_delivery(
        product_type="website",
        requirements=[_req("must"), _req("must"), _budget("Есть ориентир до ~50 тыс. ₽")],
        fetch_market=False,
    )
    assert est.budget_fit == "above"
    report = render_template_report(est)
    assert report.method == REPORT_TEMPLATE_METHOD
    assert "Почему столько стоит" in report.title
    assert "не входит" in report.body.lower() or "Не входит" in report.body
    assert DISCLAIMER_RU in report.body
    assert "50" in report.body
    assert "Admin analytics" not in report.body


def test_stub_llm_falls_back_to_template():
    est = estimate_client_delivery(product_type="telegram_bot", fetch_market=False)
    report = write_client_estimate_report(est, complete_json=lambda *_a, **_k: None)
    assert report.method == REPORT_TEMPLATE_METHOD
    assert report.body

    llm_report = write_client_estimate_report(
        est,
        complete_json=lambda *_a, **_k: {
            "title": "Разбор сметы",
            "body": "LLM написал, почему столько часов.",
        },
    )
    assert llm_report.method == REPORT_LLM_METHOD
    assert "LLM написал" in llm_report.body


def test_market_fetch_requires_https_allowlist():
    assert _host_allowlisted("http://example.com/rates.json", ["example.com"]) is False
    assert _host_allowlisted("https://evil.test/rates.json", ["rates.example"]) is False
    assert _host_allowlisted("https://rates.example/v1.json", ["rates.example"]) is True
    table = load_market_table(fetch=False)
    assert table["fetched"] is False
    assert "ru_cis_freelance" in table["bands"]


def test_work_items_include_open_questions_and_risks():
    items = collect_work_items(
        product_type="rest_service",
        requirements=[_req("must")],
        open_questions=[SimpleNamespace(id="q", name="Что с оплатой?", status="open")],
        risks=[SimpleNamespace(id="rk", name="Нет API", status="active")],
    )
    kinds = {item["kind"] for item in items}
    assert "base" in kinds
    assert "open_question" in kinds
    assert "risk" in kinds


def test_approve_persists_client_estimate_and_confirm_unlocks_ready(client, monkeypatch):
    sent: list[str] = []

    def fake_owner(text: str, *, parse_mode: str | None = "Markdown") -> bool:
        sent.append(text)
        return True

    def fake_customer(chat_id: str, text: str) -> bool:
        sent.append(f"{chat_id}:{text}")
        return True

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "4242")
    from core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "integrations.telegram.notify.send_owner_telegram",
        fake_owner,
    )
    monkeypatch.setattr(
        "integrations.telegram.notify.send_customer_telegram",
        fake_customer,
    )

    created = client.post(
        "/projects",
        json={
            "name": "Пекарня смета",
            "product_type": "website",
            "customer_telegram_id": "88002",
        },
    )
    project_id = created.json()["id"]
    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"

    hitl = client.post(
        f"/projects/{project_id}/hitl",
        json={
            "action": "approve",
            "note": "Ок для сметы",
            "actor_telegram_id": "4242",
        },
    )
    assert hitl.status_code == 200
    assert hitl.json()["project_status"] == "WAITING_CLIENT_ESTIMATE"

    tz = client.get(f"/projects/{project_id}/artifacts/draft-tz").json()
    assert tz["estimate"]["method"] == "heuristic_v1"
    assert tz["client_estimate"]["method"] == METHOD
    assert tz["client_estimate"]["status"] == "pending"
    assert tz["client_estimate"]["cost"] != tz["estimate"]["cost"]
    assert tz["client_estimate_report"]["body"]
    assert DISCLAIMER_RU in tz["client_estimate"]["disclaimer"]

    ws = client.get(
        f"/projects/{project_id}/workspace",
        params={"customer_telegram_id": "88002"},
    ).json()
    assert ws["status"] == "WAITING_CLIENT_ESTIMATE"
    assert ws["client_estimate"]["formatted_cost"]
    assert ws["client_estimate"]["report"]["body"]

    got = client.get(
        f"/projects/{project_id}/client-estimate",
        params={"customer_telegram_id": "88002"},
    )
    assert got.status_code == 200
    assert got.json()["client_estimate"]["hours"] > 0

    blocked = client.post(f"/projects/{project_id}/coordinator/planner", json={})
    assert blocked.status_code == 400

    confirm = client.post(
        f"/projects/{project_id}/client-estimate/confirm",
        json={"action": "confirm", "customer_telegram_id": "88002"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["project_status"] == "READY"
    assert confirm.json()["client_estimate"]["status"] == "confirmed"

    tz2 = client.get(f"/projects/{project_id}/artifacts/draft-tz").json()
    assert tz2["estimate"]["cost"] == tz["estimate"]["cost"]
    assert tz2["client_estimate"]["status"] == "confirmed"

    blob = "\n".join(sent)
    assert "88002" in blob
    assert "Смета" in blob
    assert "подтвердил" in blob.lower()

    get_settings.cache_clear()


def test_discuss_returns_waiting_customer_then_can_confirm(client):
    created = client.post(
        "/projects",
        json={
            "name": "Обсуждение сметы",
            "product_type": "telegram_bot",
            "customer_telegram_id": "88003",
        },
    )
    project_id = created.json()["id"]
    _drive_discovery_to_owner(client, project_id)
    client.post(f"/projects/{project_id}/hitl", json={"action": "approve"})

    discuss = client.post(
        f"/projects/{project_id}/client-estimate/discuss",
        json={"action": "discuss", "customer_telegram_id": "88003"},
    )
    assert discuss.status_code == 200
    assert discuss.json()["project_status"] == "WAITING_CUSTOMER"
    assert discuss.json()["client_estimate"]["status"] == "discuss_requested"

    later = client.post(
        f"/projects/{project_id}/client-estimate/confirm",
        json={"action": "confirm", "customer_telegram_id": "88003"},
    )
    assert later.status_code == 200
    assert later.json()["project_status"] == "READY"


def test_compose_client_estimate_markdown_reuses_tz_export_pipeline():
    from core.tz_document import export_markdown_file

    est = estimate_client_delivery(
        product_type="website",
        requirements=[_req("must", name="Форма заявки")],
        fetch_market=False,
    )
    report = render_template_report(est)
    project = SimpleNamespace(name="Пекарня", product_type="website")
    markdown = compose_client_estimate_markdown(project, est, report)
    assert "# Смета — Пекарня" in markdown
    assert DISCLAIMER_RU in markdown
    assert "Форма заявки" in markdown
    assert "Почему столько стоит" in markdown

    md, media, name = export_markdown_file(markdown, "pekarnia-smeta", "md")
    assert name.endswith(".md")
    assert "text/markdown" in media
    assert "Смета — Пекарня" in md.decode("utf-8")

    pdf, pdf_media, pdf_name = export_markdown_file(markdown, "pekarnia-smeta", "pdf")
    assert pdf_name.endswith(".pdf")
    assert pdf_media == "application/pdf"
    assert pdf.startswith(b"%PDF")

    docx, docx_media, docx_name = export_markdown_file(markdown, "pekarnia-smeta", "docx")
    assert docx_name.endswith(".docx")
    assert docx[:2] == b"PK"
    assert "wordprocessingml" in docx_media


def test_customer_estimate_export_and_send(client, monkeypatch):
    delivered: list[tuple] = []

    def fake_doc(chat_id, *, data, filename, caption=None):
        delivered.append((chat_id, filename, caption, len(data or b"")))
        return {"ok": True, "chat_id": str(chat_id), "message_id": 202, "bot_username": "asf_bot"}

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    from core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "integrations.telegram.notify.send_customer_telegram_document",
        fake_doc,
    )

    created = client.post(
        "/projects",
        json={
            "name": "Смета файл",
            "product_type": "website",
            "customer_telegram_id": "88004",
        },
    )
    project_id = created.json()["id"]
    too_soon = client.get(
        f"/projects/{project_id}/estimate-export",
        params={"format": "md", "customer_telegram_id": "88004"},
    )
    assert too_soon.status_code == 409

    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"
    hitl = client.post(f"/projects/{project_id}/hitl", json={"action": "approve"})
    assert hitl.status_code == 200

    forbidden = client.get(
        f"/projects/{project_id}/estimate-export",
        params={"format": "md", "customer_telegram_id": "999"},
    )
    assert forbidden.status_code == 403

    md = client.get(
        f"/projects/{project_id}/estimate-export",
        params={"format": "md", "customer_telegram_id": "88004"},
    )
    assert md.status_code == 200
    text = md.content.decode("utf-8")
    assert "Смета — Смета файл" in text
    assert DISCLAIMER_RU in text
    assert "attachment" in md.headers.get("content-disposition", "")

    pdf = client.get(
        f"/projects/{project_id}/estimate-export",
        params={"format": "pdf", "customer_telegram_id": "88004"},
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    sent = client.post(
        f"/projects/{project_id}/estimate-send",
        params={"format": "md", "customer_telegram_id": "88004"},
    )
    assert sent.status_code == 200
    assert sent.json()["sent"] is True
    assert sent.json()["message_id"] == 202
    assert sent.json()["chat_id"] == "88004"
    assert delivered
    assert delivered[-1][0] == "88004"
    assert "Смета" in (delivered[-1][2] or "")
    get_settings.cache_clear()
