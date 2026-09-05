from __future__ import annotations

import os
import subprocess
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
    assert values["DISCOVERY_ENGINE"] == "auto"


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


def test_telegram_proxy_and_ip_mode_go_to_env():
    values = build_env_values(
        _base_raw(TELEGRAM_PROXY="http://127.0.0.1:8888", ASF_TELEGRAM_IP="4")
    )
    assert values["HTTPS_PROXY"] == "http://127.0.0.1:8888"
    assert values["HTTP_PROXY"] == "http://127.0.0.1:8888"
    assert values["TELEGRAM_PROXY"] == "http://127.0.0.1:8888"
    assert values["ASF_TELEGRAM_IP"] == "4"
    assert values["NO_PROXY"] == "localhost,127.0.0.1,db"
    bad = build_env_values(_base_raw(ASF_TELEGRAM_IP="99"))
    assert bad["ASF_TELEGRAM_IP"] == "auto"


def test_llm_http_proxy_alias_fills_https_and_http_for_ai_and_telegram():
    values = build_env_values(_base_raw(LLM_HTTP_PROXY="http://127.0.0.1:1080"))
    assert values["HTTPS_PROXY"] == "http://127.0.0.1:1080"
    assert values["HTTP_PROXY"] == "http://127.0.0.1:1080"
    assert values["LLM_HTTP_PROXY"] == "http://127.0.0.1:1080"


def test_https_proxy_alone_is_enough_no_second_secret():
    values = build_env_values(_base_raw(HTTPS_PROXY="http://127.0.0.1:3128"))
    assert values["HTTPS_PROXY"] == "http://127.0.0.1:3128"
    assert values["HTTP_PROXY"] == "http://127.0.0.1:3128"
    assert values["TELEGRAM_PROXY"] == ""


def test_empty_github_secrets_keep_existing_vps_ai_proxy(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("HTTPS_PROXY=http://127.0.0.1:3128\n", encoding="utf-8")
    monkeypatch.setenv("ASF_ENV_PATH", str(env_path))
    for key in (
        "TELEGRAM_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "LLM_HTTP_PROXY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")
    monkeypatch.setenv("DOMAIN_MINIAPP", "mini.example.com")
    monkeypatch.setenv("CONSOLE_TOKEN", "owner-token")
    values = build_env_values()
    assert values["HTTPS_PROXY"] == "http://127.0.0.1:3128"
    assert values["HTTP_PROXY"] == "http://127.0.0.1:3128"
    assert os.environ.get("HTTPS_PROXY") in {None, ""}


def test_render_env_file_contains_keys():
    text = render_env_file(build_env_values(_base_raw()))
    assert "ASF_ENV=production" in text
    assert "MINIAPP_URL=https://mini.example.com/miniapp/" in text
    assert "ASF_ESTIMATE_HOURLY_RATE=3000" in text
    assert "ASF_ESTIMATE_CURRENCY=RUB" in text
    assert "STUDIO_NAME=" in text
    assert "OWNER_CONTACT_NAME=" in text
    assert "ASF_INTERVENTION_TTL_HOURS=72" in text
    assert "CURSOR_CLOUD_API_URL=https://api.cursor.com" in text
    values = build_env_values(_base_raw())
    assert values["HTTPS_PROXY"] == ""
    assert values["EGRESS_SSH_HOST"] == ""
    assert "localhost" in values["NO_PROXY"]


def test_egress_host_sets_container_http_proxy():
    values = build_env_values(_base_raw(EGRESS_SSH_HOST="5.180.43.218"))
    assert values["EGRESS_SSH_HOST"] == "5.180.43.218"
    assert values["EGRESS_SSH_USER"] == "root"
    assert values["EGRESS_SSH_PORT"] == "22"
    assert values["HTTPS_PROXY"] == "http://egress:8888"
    assert values["HTTP_PROXY"] == "http://egress:8888"
    assert values["ALL_PROXY"] == "http://egress:8888"
    assert "egress" in values["NO_PROXY"]
    assert "db" in values["NO_PROXY"]


def test_prod_compose_defines_egress_profile():
    text = (Path(__file__).resolve().parents[1] / "docker-compose.prod.yml").read_text(
        encoding="utf-8"
    )
    assert 'profiles: ["egress"]' in text
    assert "dockerfile: docker/Dockerfile.egress" in text
    assert "HTTPS_PROXY: ${HTTPS_PROXY:-}" in text


def test_nginx_vhost_is_not_default_server():
    block = render_server_block("mini.example.com", "127.0.0.1:18000")
    assert "listen 80;" in block
    assert "listen 80 default_server" not in block
    assert "server_name mini.example.com;" in block
    assert "proxy_pass http://127.0.0.1:18000;" in block
    assert "proxy_set_header X-Console-Token $http_x_console_token;" in block
    assert "proxy_set_header Authorization $http_authorization;" in block
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


def test_telegram_egress_scripts_do_not_print_secrets():
    diagnose = Path("deploy/diagnose_telegram_egress.sh").read_text(encoding="utf-8")
    hotfix = Path("deploy/hotfix_telegram_ipv4.sh").read_text(encoding="utf-8")
    tunnel = Path("deploy/setup_egress_tunnel.sh").read_text(encoding="utf-8")
    assert "api.telegram.org" in diagnose
    assert "VERDICT=" in diagnose
    assert "TELEGRAM_BOT_TOKEN" not in diagnose
    assert "TELEGRAM_BOT_TOKEN" not in hotfix
    assert "extra_hosts" in hotfix
    assert "EGRESS_SSH_PASSWORD" not in diagnose
    assert 'echo "$PUBKEY"' not in tunnel
    assert 'echo "$EGRESS_SSH_PASSWORD"' not in tunnel


def test_asf_sudo_uses_env_so_apt_prefixes_work():
    for rel in (
        "deploy/setup_egress_tunnel.sh",
        "deploy/setup_egress_exit.sh",
        "deploy/setup_proxy.sh",
        "deploy/remote_up.sh",
    ):
        text = Path(rel).read_text(encoding="utf-8")
        assert 'env "$@"' in text, rel


def test_egress_exit_config_keeps_systemd_pidfile():
    text = Path("deploy/setup_egress_exit.sh").read_text(encoding="utf-8")
    assert 'PidFile "/run/tinyproxy/tinyproxy.pid"' in text
    assert 'LogFile "/var/log/tinyproxy/tinyproxy.log"' in text
    assert "127.0.0.1:8888" in text
    assert "systemctl enable --now tinyproxy" not in text


def test_asf_sudo_env_prefix_is_not_executed_as_command():
    script = r"""
    set -euo pipefail
    asf_sudo() {
      if [[ "$(id -u)" -eq 0 ]]; then
        env "$@"
      else
        env "$@"
      fi
    }
    out="$(asf_sudo DEBIAN_FRONTEND=noninteractive /bin/sh -c 'printf %s "$DEBIAN_FRONTEND"')"
    test "$out" = "noninteractive"
    """
    subprocess.run(["bash", "-c", script], check=True)
