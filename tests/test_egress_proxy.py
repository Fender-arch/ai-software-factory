"""Outbound proxy URL selection: Telegram uses the same hop as AI httpx."""

from __future__ import annotations

from pathlib import Path

from core.config import Settings
from core.egress import (
    existing_proxy_values,
    parse_env_file_values,
    resolve_outbound_proxy_url,
)
from integrations.telegram.notify import telegram_http_client, telegram_proxy_url


def test_resolve_prefers_telegram_then_https_then_llm_alias():
    assert (
        resolve_outbound_proxy_url(
            {
                "TELEGRAM_PROXY": "http://127.0.0.1:1",
                "HTTPS_PROXY": "http://127.0.0.1:2",
                "LLM_HTTP_PROXY": "http://127.0.0.1:3",
            }
        )
        == "http://127.0.0.1:1"
    )
    assert (
        resolve_outbound_proxy_url(
            {
                "HTTPS_PROXY": "http://127.0.0.1:2",
                "LLM_HTTP_PROXY": "http://127.0.0.1:3",
            }
        )
        == "http://127.0.0.1:2"
    )
    assert (
        resolve_outbound_proxy_url({"LLM_HTTP_PROXY": "http://127.0.0.1:3"})
        == "http://127.0.0.1:3"
    )
    assert resolve_outbound_proxy_url({"HTTP_PROXY": "http://127.0.0.1:4"}) == (
        "http://127.0.0.1:4"
    )
    assert resolve_outbound_proxy_url({"ALL_PROXY": "http://127.0.0.1:5"}) == (
        "http://127.0.0.1:5"
    )
    assert resolve_outbound_proxy_url({}) == ""
    assert resolve_outbound_proxy_url({"HTTPS_PROXY": "SET_ME", "ALL_PROXY": "  "}) == ""


def test_resolve_falls_back_to_existing_env_mapping():
    incoming = {"HTTPS_PROXY": "", "TELEGRAM_PROXY": ""}
    existing = {"HTTPS_PROXY": "http://127.0.0.1:3128"}
    assert (
        resolve_outbound_proxy_url(incoming, existing) == "http://127.0.0.1:3128"
    )


def test_settings_outbound_http_proxy_matches_resolver():
    settings = Settings(
        telegram_proxy="",
        https_proxy="http://127.0.0.1:8080",
        llm_http_proxy="http://127.0.0.1:9",
    )
    assert settings.outbound_http_proxy() == "http://127.0.0.1:8080"


def test_parse_and_existing_proxy_values_from_vps_env(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        "# Generated\nHTTPS_PROXY=http://127.0.0.1:3128\nGROQ_API_KEY=secret-not-a-proxy\n",
        encoding="utf-8",
    )
    parsed = parse_env_file_values(path.read_text(encoding="utf-8"))
    assert parsed["GROQ_API_KEY"] == "secret-not-a-proxy"
    found = existing_proxy_values(path)
    assert found == {"HTTPS_PROXY": "http://127.0.0.1:3128"}
    assert "secret-not-a-proxy" not in found


def test_telegram_proxy_url_reads_https_proxy(monkeypatch):
    for key in (
        "TELEGRAM_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "LLM_HTTP_PROXY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:3128")
    assert telegram_proxy_url() == "http://127.0.0.1:3128"


def _client_proxy_host_port(client) -> tuple[str, int] | None:
    for transport in client._mounts.values():
        if transport is None:
            continue
        pool = getattr(transport, "_pool", None)
        proxy = getattr(pool, "_proxy_url", None)
        if proxy is None:
            continue
        host = getattr(proxy, "host", None)
        port = getattr(proxy, "port", None)
        if host is None:
            continue
        if isinstance(host, (bytes, bytearray)):
            host = host.decode()
        return str(host), int(port)
    return None


def test_telegram_http_client_passes_https_proxy_not_ipv4_transport(monkeypatch):
    for key in (
        "TELEGRAM_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "LLM_HTTP_PROXY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:3128")
    monkeypatch.setenv("ASF_TELEGRAM_IP", "4")
    client = telegram_http_client(3.0)
    try:
        assert _client_proxy_host_port(client) == ("127.0.0.1", 3128)
        pool = getattr(client._transport, "_pool", None)
        local = getattr(pool, "_local_address", None) if pool is not None else None
        assert local != "0.0.0.0"
    finally:
        client.close()


def test_telegram_http_client_llm_alias_when_no_https_proxy(monkeypatch):
    for key in (
        "TELEGRAM_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "LLM_HTTP_PROXY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_HTTP_PROXY", "http://127.0.0.1:1080")
    client = telegram_http_client(2.0)
    try:
        assert _client_proxy_host_port(client) == ("127.0.0.1", 1080)
    finally:
        client.close()
