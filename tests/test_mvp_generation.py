"""EPIC-04: HITL → Planner → export → website smoke."""

from __future__ import annotations

from tests.test_discovery import _drive_discovery_to_owner
from discovery.fsm import DiscoveryStage


def _reach_waiting_owner(client) -> str:
    created = client.post(
        "/projects", json={"name": "Bakery Site", "product_type": "website"}
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    last = _drive_discovery_to_owner(client, project_id)
    assert last.json()["project_status"] == "WAITING_OWNER"
    assert last.json()["discovery_stage"] == DiscoveryStage.READY_FOR_OWNER.value
    return project_id


def test_hitl_approve_sets_ready(client):
    project_id = _reach_waiting_owner(client)

    review = client.get(f"/projects/{project_id}/hitl/review")
    assert review.status_code == 200
    assert review.json()["artifact_id"]
    assert "Draft TZ" in (review.json().get("draft_preview") or "")

    bad = client.post(
        f"/projects/{project_id}/coordinator/planner",
        json={},
    )
    assert bad.status_code == 400

    hitl = client.post(
        f"/projects/{project_id}/hitl",
        json={"action": "approve", "note": "LGTM for MVP"},
    )
    assert hitl.status_code == 200
    body = hitl.json()
    assert body["action"] == "approve"
    assert body["project_status"] == "READY"
    assert body["human_decision_required"] is False

    project = client.get(f"/projects/{project_id}").json()
    assert project["status"] == "READY"

    tz = client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.json()["status"] == "approved"


def test_hitl_request_changes_and_reject(client):
    project_id = _reach_waiting_owner(client)
    changes = client.post(
        f"/projects/{project_id}/hitl",
        json={"action": "request_changes", "note": "Clarify CTA destination"},
    )
    assert changes.status_code == 200
    assert changes.json()["project_status"] == "WAITING_CUSTOMER"
    assert changes.json()["human_decision_required"] is True

    # Fresh project for reject
    project_id2 = _reach_waiting_owner(client)
    rejected = client.post(
        f"/projects/{project_id2}/hitl",
        json={"action": "reject", "note": "Out of scope"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["project_status"] == "ARCHIVED"


def test_hitl_rejects_non_owner_when_configured(client, monkeypatch):
    from core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "999001")
    get_settings.cache_clear()

    project_id = _reach_waiting_owner(client)
    denied = client.post(
        f"/projects/{project_id}/hitl",
        json={
            "action": "approve",
            "actor_telegram_id": "111",
        },
    )
    assert denied.status_code == 400
    assert "owner" in denied.json()["detail"].lower()

    ok = client.post(
        f"/projects/{project_id}/hitl",
        json={
            "action": "approve",
            "actor_telegram_id": "999001",
        },
    )
    assert ok.status_code == 200
    get_settings.cache_clear()
    monkeypatch.delenv("OWNER_TELEGRAM_ID", raising=False)
    get_settings.cache_clear()


def test_planner_and_export_formats(client):
    project_id = _reach_waiting_owner(client)
    assert (
        client.post(
            f"/projects/{project_id}/hitl", json={"action": "approve"}
        ).status_code
        == 200
    )

    planned = client.post(
        f"/projects/{project_id}/coordinator/planner",
        json={},
    )
    assert planned.status_code == 200
    output = planned.json()["output"]
    assert len(output["tasks"]) >= 3
    assert output["reused_existing"] is False
    assert any(c["id"] == "has_work_items" and c["ok"] for c in output["exit_checklist"])

    # Idempotent reuse
    again = client.post(
        f"/projects/{project_id}/coordinator/planner",
        json={},
    )
    assert again.json()["output"]["reused_existing"] is True

    md = client.get(f"/projects/{project_id}/export/tasks?format=markdown")
    assert md.status_code == 200
    md_body = md.json()
    assert md_body["task_count"] >= 3
    assert "Cursor tasks" in md_body["content"]
    assert "templates/website.md" in md_body["content"]
    assert "Acceptance criteria" in md_body["content"]

    js = client.get(f"/projects/{project_id}/export/tasks?format=json")
    assert js.status_code == 200
    payload = js.json()
    assert payload["format"] == "json"
    assert '"tasks"' in payload["content"]
    assert payload["tasks"][0]["title"]


def test_website_mvp_smoke_end_to_end(client):
    """Smoke: Telegram-equivalent API path for website → Cursor export."""
    project_id = _reach_waiting_owner(client)

    tz = client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.status_code == 200
    assert "bakery" in tz.json()["content"].lower() or "website" in tz.json()["content"].lower()

    hitl = client.post(
        f"/projects/{project_id}/hitl",
        json={"action": "approve", "note": "Ship brochure MVP"},
    )
    assert hitl.status_code == 200
    assert hitl.json()["project_status"] == "READY"

    planned = client.post(
        f"/projects/{project_id}/coordinator/planner",
        json={},
    )
    assert planned.status_code == 200
    tasks = planned.json()["output"]["tasks"]
    titles = " ".join(t["title"].lower() for t in tasks)
    assert "website" in titles or "scaffold" in titles
    assert "contact" in titles or "cta" in titles or "page" in titles

    exported = client.get(f"/projects/{project_id}/export/tasks?format=markdown")
    assert exported.status_code == 200
    content = exported.json()["content"]
    assert "product-templates.mdc" in content
    assert exported.json()["task_count"] == len(tasks)

    # Tasks reference requirements where possible
    js = client.get(f"/projects/{project_id}/export/tasks?format=json")
    task0 = js.json()["tasks"][0]
    assert task0["status"] == "NEW"
    assert isinstance(task0.get("requirement_ids"), list)
