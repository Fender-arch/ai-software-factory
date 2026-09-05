"""Telegram sendDocument: customer DM chat_id, ok/message_id, no token in logs."""

from __future__ import annotations

import logging

import httpx

from core.config import get_settings
from integrations.telegram.notify import (
    customer_dm_chat_id,
    reset_telegram_identity_cache,
    send_customer_telegram_document,
    telegram_bot_username,
)


def _fake_client(handler):
    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data=None, files=None):
            return handler(url, data or {}, files or {})

    return FakeClient


def test_customer_dm_chat_id_prefers_actor_not_owner_or_group():
    assert (
        customer_dm_chat_id(
            project_customer_telegram_id="-100123",
            actor_telegram_id="88001",
            owner_telegram_id="1",
        )
        == "88001"
    )
    assert (
        customer_dm_chat_id(
            project_customer_telegram_id="88001",
            actor_telegram_id=None,
            owner_telegram_id="1",
        )
        == "88001"
    )
    assert (
        customer_dm_chat_id(
            project_customer_telegram_id=None,
            actor_telegram_id=None,
            owner_telegram_id="1",
        )
        is None
    )
    assert (
        customer_dm_chat_id(
            project_customer_telegram_id="@shop",
            actor_telegram_id="",
            owner_telegram_id="1",
        )
        is None
    )


def test_send_document_requires_ok_message_id_and_customer_chat(monkeypatch, caplog):
    posted: list[dict] = []

    def handler(url, data, files):
        posted.append({"url": url, "data": data, "files": files})
        if url.endswith("/getMe"):
            return httpx.Response(
                200, json={"ok": True, "result": {"id": 9, "username": "asf_factory_bot"}}
            )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 77,
                    "chat": {"id": 88001, "type": "private"},
                    "document": {"file_name": "tz.md"},
                },
            },
        )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-secret")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    get_settings.cache_clear()
    reset_telegram_identity_cache()
    monkeypatch.setattr("integrations.telegram.notify.httpx.Client", _fake_client(handler))

    caplog.set_level(logging.INFO)
    result = send_customer_telegram_document(
        "88001",
        data=b"# TZ\n",
        filename="Сайт-пекарни.md",
        caption="Черновик ТЗ",
    )
    assert result is not None
    assert result["ok"] is True
    assert result["message_id"] == 77
    assert result["chat_id"] == "88001"
    assert result["bot_username"] == "asf_factory_bot"
    assert result["filename"] == "tz.md"

    send = next(item for item in posted if item["url"].endswith("/sendDocument"))
    assert int(send["data"]["chat_id"]) == 88001
    assert int(send["data"]["chat_id"]) != 1
    name, payload, mime = send["files"]["document"]
    assert name == "tz.md"
    assert payload == b"# TZ\n"
    assert mime == "text/markdown"
    assert "test-token-secret" not in caplog.text
    assert "88001" in caplog.text
    get_settings.cache_clear()
    reset_telegram_identity_cache()


def test_send_document_http_200_ok_false_is_failure(monkeypatch, caplog):
    def handler(url, data, files):
        return httpx.Response(
            200,
            json={
                "ok": False,
                "error_code": 403,
                "description": "Forbidden: bot can't initiate conversation with a user",
            },
        )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-secret")
    get_settings.cache_clear()
    reset_telegram_identity_cache()
    monkeypatch.setattr("integrations.telegram.notify.httpx.Client", _fake_client(handler))

    caplog.set_level(logging.WARNING)
    result = send_customer_telegram_document(
        "88001",
        data=b"# TZ\n",
        filename="tz.md",
    )
    assert result["ok"] is False
    assert "can't initiate" in result["description"]
    assert "test-token-secret" not in caplog.text
    assert "88001" in caplog.text
    assert "can't initiate" in caplog.text
    get_settings.cache_clear()
    reset_telegram_identity_cache()


def test_send_document_rejects_wrong_result_chat(monkeypatch):
    def handler(url, data, files):
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"message_id": 1, "chat": {"id": 1, "type": "private"}},
            },
        )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()
    reset_telegram_identity_cache()
    monkeypatch.setattr("integrations.telegram.notify.httpx.Client", _fake_client(handler))

    result = send_customer_telegram_document(
        "88001",
        data=b"# TZ\n",
        filename="tz.md",
    )
    assert result["ok"] is False
    assert "не в чат заказчика" in result["description"]
    get_settings.cache_clear()
    reset_telegram_identity_cache()


def test_telegram_bot_username_cached(monkeypatch):
    calls = {"n": 0}

    def handler(url, data, files):
        calls["n"] += 1
        return httpx.Response(
            200, json={"ok": True, "result": {"username": "asf_factory_bot"}}
        )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    get_settings.cache_clear()
    reset_telegram_identity_cache()
    monkeypatch.setattr("integrations.telegram.notify.httpx.Client", _fake_client(handler))
    assert telegram_bot_username() == "asf_factory_bot"
    assert telegram_bot_username() == "asf_factory_bot"
    assert calls["n"] == 1
    get_settings.cache_clear()
    reset_telegram_identity_cache()
