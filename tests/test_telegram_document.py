"""Telegram sendDocument: customer DM chat_id, ok/message_id, no token in logs."""

from __future__ import annotations

import logging

import httpx

from core.config import get_settings
from integrations.telegram.notify import (
    MSG_TELEGRAM_BAD_TOKEN,
    MSG_TELEGRAM_START_REQUIRED,
    MSG_TELEGRAM_UNREACHABLE,
    TELEGRAM_UNREACHABLE,
    classify_telegram_document_error,
    customer_dm_chat_id,
    diagnose_telegram_bot_api,
    probe_telegram_bot_api,
    reset_telegram_identity_cache,
    send_customer_telegram_document,
    telegram_bot_username,
    telegram_http_client,
)


def _fake_client(handler):
    class FakeClient:
        def __init__(self, timeout=None, **kwargs):
            self.timeout = timeout
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data=None, files=None):
            return handler(url, data or {}, files or {})

        def get(self, url):
            return handler(url, {}, {})

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


def test_classify_telegram_document_error_splits_causes():
    assert (
        classify_telegram_document_error(
            "сеть до Telegram недоступна", error_kind="transport"
        )
        == MSG_TELEGRAM_UNREACHABLE
    )
    assert (
        classify_telegram_document_error(TELEGRAM_UNREACHABLE)
        == MSG_TELEGRAM_UNREACHABLE
    )
    assert "не ваш интернет" in MSG_TELEGRAM_UNREACHABLE
    assert "сеть до Telegram недоступна" not in MSG_TELEGRAM_UNREACHABLE
    assert (
        classify_telegram_document_error(
            "Forbidden: bot can't initiate conversation with a user",
            http_status=403,
        )
        == MSG_TELEGRAM_START_REQUIRED
    )
    assert (
        classify_telegram_document_error("Bad Request: chat not found")
        == MSG_TELEGRAM_START_REQUIRED
    )
    assert (
        classify_telegram_document_error("Unauthorized", http_status=401)
        == MSG_TELEGRAM_BAD_TOKEN
    )
    assert (
        classify_telegram_document_error("Unauthorized: invalid token")
        == MSG_TELEGRAM_BAD_TOKEN
    )
    assert (
        classify_telegram_document_error("Bad Request: file is too big")
        == "Bad Request: file is too big"
    )


def test_send_document_transport_error_is_server_egress(monkeypatch, caplog):
    class BoomClient:
        def __init__(self, timeout=None, **kwargs):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data=None, files=None):
            raise httpx.ConnectError("dns")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-secret")
    get_settings.cache_clear()
    reset_telegram_identity_cache()
    monkeypatch.setattr("integrations.telegram.notify.httpx.Client", BoomClient)

    caplog.set_level(logging.WARNING)
    result = send_customer_telegram_document(
        "88001",
        data=b"# TZ\n",
        filename="tz.md",
    )
    assert result["ok"] is False
    assert result["error_kind"] == "transport"
    assert result["description"] == TELEGRAM_UNREACHABLE
    assert "сеть до Telegram недоступна" not in result["description"]
    assert "test-token-secret" not in caplog.text
    assert "ConnectError" in caplog.text
    get_settings.cache_clear()
    reset_telegram_identity_cache()


def test_send_document_401_is_unauthorized(monkeypatch, caplog):
    def handler(url, data, files):
        return httpx.Response(
            401,
            json={"ok": False, "error_code": 401, "description": "Unauthorized"},
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
    assert result["error_kind"] == "unauthorized"
    assert result["http_status"] == 401
    assert result["description"] == "Unauthorized"
    assert "test-token-secret" not in caplog.text
    assert "Unauthorized" in caplog.text
    get_settings.cache_clear()
    reset_telegram_identity_cache()


def test_telegram_http_client_prefers_ipv4_when_asked(monkeypatch):
    monkeypatch.setenv("ASF_TELEGRAM_IP", "4")
    client = telegram_http_client(3.0)
    try:
        transport = client._transport
        pool = getattr(transport, "_pool", None)
        local = getattr(pool, "_local_address", None) if pool is not None else None
        assert local == "0.0.0.0"
    finally:
        client.close()


def test_diagnose_telegram_bot_api_no_token_in_output(monkeypatch, caplog):
    def handler(url, data, files):
        if str(url).rstrip("/").endswith("api.telegram.org"):
            return httpx.Response(200, text="ok")
        return httpx.Response(
            200,
            json={"ok": True, "result": {"id": 9, "username": "asf_factory_bot"}},
        )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-secret")
    get_settings.cache_clear()
    reset_telegram_identity_cache()
    monkeypatch.setattr("integrations.telegram.notify.httpx.Client", _fake_client(handler))

    caplog.set_level(logging.INFO)
    assert probe_telegram_bot_api()["ok"] is True
    report = diagnose_telegram_bot_api()
    assert report["egress_ok"] is True
    assert report["bot_ok"] is True
    assert report["bot_username"] == "asf_factory_bot"
    dumped = str(report)
    assert "test-token-secret" not in dumped
    assert "test-token-secret" not in caplog.text
    get_settings.cache_clear()
    reset_telegram_identity_cache()
