def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "asf-api"


def test_health_telegram_diagnose_no_token(client, monkeypatch):
    from core.config import get_settings

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "integrations.telegram.notify.diagnose_telegram_bot_api",
        lambda: {
            "egress_ok": False,
            "egress_http_status": None,
            "egress_error": "ConnectError",
            "bot_ok": False,
            "bot_username": None,
            "bot_http_status": None,
            "bot_description": "ConnectError",
        },
    )
    response = client.get("/health/telegram")
    assert response.status_code == 200
    data = response.json()
    assert data["egress_ok"] is False
    assert data["egress_error"] == "ConnectError"
    assert data["bot_ok"] is False
    dumped = response.text
    assert "test-token-secret" not in dumped
    get_settings.cache_clear()
