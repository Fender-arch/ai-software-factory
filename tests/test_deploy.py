from __future__ import annotations

from pathlib import Path

import pytest

from deploy.render_nginx import (
    normalize_domain,
    render_server_block,
    site_filenames,
    write_sites,
)
from deploy.write_env import build_env_values, miniapp_https_url, render_env_file


def _base_raw(**overrides: str) -> dict[str, str]:
    raw = {
        "POSTGRES_PASSWORD": "s3cret",
        "DOMAIN_MINIAPP": "mini.example.com",
        "DOMAIN_CONSOLE": "tz.example.com",
        "CONSOLE_TOKEN": "owner-token",
        "TELEGRAM_BOT_TOKEN": "123:abc",
    }
    raw.update(overrides)
    return raw


def test_miniapp_url_normalizes_scheme_and_path():
    assert miniapp_https_url("https://mini.example.com/foo") == "https://mini.example.com/miniapp/"
    assert miniapp_https_url("mini.example.com") == "https://mini.example.com/miniapp/"


def test_build_env_values_sets_production_and_quoted_db_url():
    values = build_env_values(_base_raw())
    assert values["ASF_ENV"] == "production"
    assert values["ASF_DEBUG"] == "false"
    assert values["MINIAPP_URL"] == "https://mini.example.com/miniapp/"
    assert "s3cret" in values["DATABASE_URL"]
    assert values["ASF_HOST_PORT"] == "18000"


def test_invalid_host_port_falls_back_to_18000():
    assert build_env_values(_base_raw(ASF_HOST_PORT="SET_ME"))["ASF_HOST_PORT"] == "18000"
    assert build_env_values(_base_raw(ASF_HOST_PORT="not-a-port"))["ASF_HOST_PORT"] == "18000"
    assert build_env_values(_base_raw(ASF_HOST_PORT="18080"))["ASF_HOST_PORT"] == "18080"


def test_set_me_placeholders_rejected_for_required_fields():
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        build_env_values(_base_raw(POSTGRES_PASSWORD="SET_ME"))
    with pytest.raises(ValueError, match="DOMAIN_MINIAPP"):
        build_env_values(_base_raw(DOMAIN_MINIAPP="SET_ME"))
    with pytest.raises(ValueError, match="CONSOLE_TOKEN"):
        build_env_values(_base_raw(CONSOLE_TOKEN="SET_ME"))


def test_optional_set_me_becomes_empty():
    values = build_env_values(_base_raw(TELEGRAM_BOT_TOKEN="SET_ME", GROQ_API_KEY="SET_ME"))
    assert values["TELEGRAM_BOT_TOKEN"] == ""
    assert values["GROQ_API_KEY"] == ""


def test_render_env_file_contains_keys():
    text = render_env_file(build_env_values(_base_raw()))
    assert "ASF_ENV=production" in text
    assert "MINIAPP_URL=https://mini.example.com/miniapp/" in text


def test_nginx_vhost_is_not_default_server():
    block = render_server_block("mini.example.com", "127.0.0.1:18000")
    assert "listen 80;" in block
    assert "listen 80 default_server" not in block
    assert "server_name mini.example.com;" in block
    assert "proxy_pass http://127.0.0.1:18000;" in block
    assert "Permissions-Policy" in block
    assert "microphone=(self)" in block
    assert "listen 80;" in block
    assert ".well-known/acme-challenge/" in block
    assert "listen 443" not in block


def test_tls_vhost_uses_letsencrypt_and_is_not_default():
    block = render_server_block("ai-sf-fac.duckdns.org", "127.0.0.1:18000", tls=True)
    assert "listen 443 ssl;" in block
    assert "listen 443 ssl default_server" not in block
    assert "ssl_certificate /etc/letsencrypt/live/ai-sf-fac.duckdns.org/fullchain.pem;" in block
    assert "Permissions-Policy" in block
    assert "return 301 https://$host$request_uri;" in block


def test_same_domain_emits_one_site_file(tmp_path: Path):
    assert site_filenames("app.example.com", "app.example.com") == {"asf.conf": "app.example.com"}
    paths = write_sites(tmp_path, "app.example.com", "https://app.example.com", "127.0.0.1:18000")
    assert len(paths) == 1
    assert paths[0].name == "asf.conf"


def test_normalize_domain_strips_url():
    assert normalize_domain("https://TZ.Example.com/console/") == "tz.example.com"
