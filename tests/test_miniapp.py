"""EPIC-05 Mini App customer APIs."""

import io
import uuid

from apps.api.main import app
from core.db import get_db
from core.models import Project, ProjectStatus


def test_miniapp_static_served(client):
    res = client.get("/miniapp/")
    assert res.status_code == 200
    assert "Создать проект" in res.text
    assert "Файл" in res.text
    assert "Голос" in res.text
    assert "choice-chips" in res.text
    assert "ws-dock" in res.text
    js = client.get("/miniapp/app.js")
    assert js.status_code == 200
    assert "scrollThreadToLatest" in js.text
    assert "scrollIntoView" not in js.text
    assert "asf-workspace" in js.text
    assert "wsRequestId" in js.text
    assert "String(ws.project_id) !== pid" in js.text
    assert "renderProgress" in js.text
    assert "discovery_progress" in js.text
    assert "20260905-xp" in res.text
    assert "ws-progress" in res.text
    assert "foundry-field" in res.text
    assert "tz-download" in res.text
    assert "Поехали" in res.text
    assert "Варианты ответа" in res.text
    assert "welcome-modal" in res.text
    assert "choices-modal" in res.text
    css = client.get("/miniapp/styles.css")
    assert css.status_code == 200
    assert ".ws-progress-track" in css.text
    assert "#2ecc71" in css.text
    assert "#5c5c5c" in css.text
    assert "--app-vh" in css.text
    assert "flex: 0 0 24%" in css.text
    assert "microphone=(self)" in (res.headers.get("permissions-policy") or "")
    assert res.headers.get("cache-control") == "no-store"


def test_miniapp_js_uses_telegram_fullscreen_and_groq_voice(client):
    js = client.get("/miniapp/app.js")
    assert js.status_code == 200
    assert "requestFullscreen" in js.text
    assert "disableVerticalSwipes" in js.text
    assert "inTelegramWebView" in js.text
    assert "tz-send" in js.text
    assert "downloadFile" in js.text
    assert "openLink" in js.text
    assert "if (inTelegramWebView()) return false" in js.text
    assert "pickRecorderMime" in js.text
    assert "visualViewport" in js.text
    assert "contentSafeAreaInset" in js.text
    assert "applyWelcomeGate" in js.text
    assert "openChoicesModal" in js.text


def test_miniapp_experience_layer_slot_and_calm_mode(client):
    res = client.get("/miniapp/")
    assert res.status_code == 200
    assert "mascot-slot" in res.text
    assert "mascot-status" in res.text
    assert "Спокойный режим" in res.text
    assert "data-calm-toggle" in res.text
    assert "experience.js" in res.text
    assert "flex: 0 0 24%" in client.get("/miniapp/styles.css").text

    xp = client.get("/miniapp/experience.js")
    assert xp.status_code == 200
    assert "asf-calm-mode" in xp.text
    assert "prefers-reduced-motion" in xp.text
    for event in (
        "idle",
        "listening",
        "thinking",
        "got_answer",
        "got_voice",
        "got_file",
        "draft_ready",
        "error",
    ):
        assert event in xp.text
    assert "@rive-app/canvas" in xp.text
    assert "mascot.riv" in xp.text

    js = client.get("/miniapp/app.js")
    assert "ASFExperience" in js.text
    assert 'xp("got_voice")' in js.text
    assert '"got_file"' in js.text
    assert '"got_answer"' in js.text
    assert "afterEvent" in js.text

    css = client.get("/miniapp/styles.css")
    assert "asf-calm" in css.text
    assert ".mascot-slot" in css.text
    assert "prefers-reduced-motion" in css.text

    foundry = client.get("/miniapp/foundry.js")
    assert "setPaused" in foundry.text
    assert "pulse" in foundry.text


def test_create_project_welcome_and_russian_question(client):
    created = client.post(
        "/projects",
        json={"name": "Автосервис", "customer_telegram_id": "7701"},
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert created.json()["status"] == "WAITING_CUSTOMER"

    ws = client.get(
        f"/projects/{pid}/workspace",
        params={"customer_telegram_id": "7701", "mode": "create"},
    )
    assert ws.status_code == 200
    messages = ws.json()["messages"]
    assert len(messages) >= 2
    welcome = messages[0]["text"]
    assert messages[0].get("meta_kind") == "welcome"
    assert "сбор требований" in welcome.lower() or "интервью" in welcome.lower()
    assert "ТЗ" in welcome
    first_q = messages[1]["text"]
    assert any(ch.isalpha() and ord(ch) > 127 for ch in first_q)
    assert "выберите вариант" not in first_q.lower()
    assert ws.json().get("discovery_choices")
    assert ws.json().get("allow_multiple") is True

    msg = client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": "7701"},
        json={"text": "Нужен бот записи для автосервиса"},
    )
    assert msg.status_code == 201
    reply = msg.json()["discovery_reply"] or ""
    assert any(ch.isalpha() and ord(ch) > 127 for ch in reply)
    assert "уже зафиксировали" not in reply.lower()


def test_new_project_chat_is_isolated_from_sibling(client):
    uid = "170410153"
    old = client.post(
        "/projects",
        json={"name": "тест", "customer_telegram_id": uid},
    ).json()
    client.post(
        f"/projects/{old['id']}/messages",
        params={"customer_telegram_id": uid},
        json={"text": "Нужен сайт для старого проекта тест"},
    )

    created = client.post(
        "/projects",
        json={"name": "Тест2.1", "customer_telegram_id": uid},
    )
    assert created.status_code == 201
    new_id = created.json()["id"]
    assert new_id != old["id"]

    ws_new = client.get(
        f"/projects/{new_id}/workspace",
        params={"customer_telegram_id": uid, "mode": "create"},
    )
    assert ws_new.status_code == 200
    body = ws_new.json()
    texts = [m["text"] for m in body["messages"]]
    assert body["project_id"] == new_id
    assert body["name"] == "Тест2.1"
    assert any("Тест2.1" in t for t in texts)
    assert all("старого проекта тест" not in t for t in texts)

    ws_old = client.get(
        f"/projects/{old['id']}/workspace",
        params={"customer_telegram_id": uid, "mode": "change"},
    ).json()
    old_texts = [m["text"] for m in ws_old["messages"]]
    assert any("Нужен сайт для старого проекта тест" in t for t in old_texts)
    assert all("Тест2.1" not in t for t in old_texts)


def test_list_projects_for_customer(client):
    a = client.post(
        "/projects",
        json={"name": "A", "customer_telegram_id": "1001"},
    ).json()
    client.post("/projects", json={"name": "B", "customer_telegram_id": "1002"})
    listed = client.get("/projects", params={"customer_telegram_id": "1001"})
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == a["id"]


def test_delete_project_removes_all_data(client):
    project = client.post(
        "/projects",
        json={"name": "ToDelete", "customer_telegram_id": "5505"},
    ).json()
    pid = project["id"]
    client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": "5505"},
        json={"text": "Нужен сайт для кафе"},
    )

    forbidden = client.delete(
        f"/projects/{pid}",
        params={"customer_telegram_id": "999"},
    )
    assert forbidden.status_code == 403

    deleted = client.delete(
        f"/projects/{pid}",
        params={"customer_telegram_id": "5505"},
    )
    assert deleted.status_code == 204

    missing = client.get(f"/projects/{pid}")
    assert missing.status_code == 404
    listed = client.get("/projects", params={"customer_telegram_id": "5505"})
    assert listed.json() == []


def test_workspace_and_message(client):
    project = client.post(
        "/projects",
        json={"name": "Cafe", "customer_telegram_id": "2002"},
    ).json()
    pid = project["id"]

    forbidden = client.get(
        f"/projects/{pid}/workspace",
        params={"customer_telegram_id": "999", "mode": "change"},
    )
    assert forbidden.status_code == 403

    msg = client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": "2002"},
        json={
            "text": (
                "Нужен лендинг для кафе: гости должны видеть меню "
                "и оставлять заявку на бронирование столика."
            )
        },
    )
    assert msg.status_code == 201

    ws = client.get(
        f"/projects/{pid}/workspace",
        params={"customer_telegram_id": "2002", "mode": "create"},
    )
    assert ws.status_code == 200
    data = ws.json()
    assert data["name"] == "Cafe"
    assert data["mode"] == "create"
    assert len(data["messages"]) >= 1
    progress = data.get("discovery_progress") or {}
    assert progress.get("total", 0) >= 8
    assert progress.get("done", 0) >= 1
    assert progress["remaining"] == progress["total"] - progress["done"]
    assert 0 <= progress.get("percent", -1) <= 100
    assert progress.get("phase") in {"interview", "review", "closing", "done"}


def test_file_attach_text_goes_through_discovery(client):
    project = client.post(
        "/projects",
        json={"name": "Docs", "customer_telegram_id": "8808"},
    ).json()
    pid = project["id"]
    content = "Клиентам нужна форма записи на сайте.".encode("utf-8")
    res = client.post(
        f"/projects/{pid}/messages/file",
        params={"customer_telegram_id": "8808"},
        files={"file": ("notes.txt", io.BytesIO(content), "text/plain")},
    )
    assert res.status_code == 201
    body = res.json()
    assert "notes.txt" in body["text"]
    assert body["discovery_reply"]
    assert any(ch.isalpha() and ord(ch) > 127 for ch in body["discovery_reply"])


def test_implementation_feedback_classifies_and_escalates(client):
    project = client.post(
        "/projects",
        json={
            "name": "ReadyApp",
            "customer_telegram_id": "3003",
            "product_type": "website",
        },
    ).json()
    pid = project["id"]

    soft = client.post(
        f"/projects/{pid}/feedback",
        json={
            "text": "Добавить форму обратной связи",
            "customer_telegram_id": "3003",
        },
    )
    assert soft.status_code == 201
    soft_body = soft.json()
    assert soft_body["kind"] == "new_requirement"
    assert soft_body["human_decision_required"] is False

    defect = client.post(
        f"/projects/{pid}/feedback",
        json={
            "text": "На сайте баг: кнопка не работает",
            "customer_telegram_id": "3003",
        },
    )
    assert defect.status_code == 201
    assert defect.json()["kind"] == "defect"

    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        row = db.get(Project, uuid.UUID(pid))
        assert row is not None
        row.status = ProjectStatus.READY
        db.commit()
    finally:
        db.close()

    contra = client.post(
        f"/projects/{pid}/feedback",
        json={
            "text": "Это не то — сайт не нужен, отмените",
            "customer_telegram_id": "3003",
        },
    )
    assert contra.status_code == 201
    body = contra.json()
    assert body["human_decision_required"] is True
    assert body["project_status"] == "WAITING_OWNER"
    assert "владельца" in body["reply_to_customer"]


def test_workspace_progress_grows_when_outline_adapts(client):
    created = client.post(
        "/projects",
        json={"name": "CardBar", "customer_telegram_id": "4404"},
    ).json()
    pid = created["id"]
    before = client.get(
        f"/projects/{pid}/workspace",
        params={"customer_telegram_id": "4404", "mode": "create"},
    ).json()["discovery_progress"]
    assert before["done"] == 0
    assert before["total"] >= 8
    assert before["percent"] == 0
    assert before["phase"] == "interview"

    client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": "4404"},
        json={
            "text": (
                "Миниапп Телеграм, визитка студии: сайты, лендинги, боты. "
                "Нужна 3D визуализация и форма заявки."
            )
        },
    )
    client.post(
        f"/projects/{pid}/messages",
        params={"customer_telegram_id": "4404"},
        json={"text": "Telegram Mini App / лендинг в Telegram"},
    )
    after = client.get(
        f"/projects/{pid}/workspace",
        params={"customer_telegram_id": "4404", "mode": "create"},
    ).json()["discovery_progress"]
    assert after["done"] >= 1
    assert after["total"] > before["total"]
    assert after["remaining"] == after["total"] - after["done"]
    assert after["percent"] == int(round((after["done"] / after["total"]) * 100))
    assert after["percent"] < 100
    assert after["phase"] == "interview"
