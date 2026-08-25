#!/usr/bin/env python3
"""Render nginx server blocks for ASF domains (never default_server)."""

from __future__ import annotations

from pathlib import Path

TEMPLATE = """\
# Managed by ASF deploy. Do not mark as default_server.
# Existing websites on this host are left untouched.
server {{
    listen 80;
    listen [::]:80;
    server_name {server_name};

    client_max_body_size 25m;

    location / {{
        proxy_pass http://{upstream};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}
}}
"""


def normalize_domain(domain: str) -> str:
    host = (domain or "").strip().rstrip("/")
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.split("/", 1)[0].lower()


def render_server_block(server_name: str, upstream: str = "127.0.0.1:18000") -> str:
    name = normalize_domain(server_name)
    if not name:
        raise ValueError("server_name is required")
    if "default_server" in name:
        raise ValueError("refusing to emit default_server")
    return TEMPLATE.format(server_name=name, upstream=upstream)


def site_filenames(miniapp_domain: str, console_domain: str) -> dict[str, str]:
    mini = normalize_domain(miniapp_domain)
    console = normalize_domain(console_domain) or mini
    if mini == console:
        return {"asf.conf": mini}
    return {"asf-miniapp.conf": mini, "asf-console.conf": console}


def write_sites(
    dest_dir: Path,
    miniapp_domain: str,
    console_domain: str,
    upstream: str = "127.0.0.1:18000",
) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, server_name in site_filenames(miniapp_domain, console_domain).items():
        path = dest_dir / filename
        path.write_text(render_server_block(server_name, upstream), encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    import os
    import sys

    dest = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    mini = os.environ.get("DOMAIN_MINIAPP") or ""
    console = os.environ.get("DOMAIN_CONSOLE") or mini
    upstream = os.environ.get("ASF_UPSTREAM") or (
        f"127.0.0.1:{os.environ.get('ASF_HOST_PORT') or '18000'}"
    )
    paths = write_sites(dest, mini, console, upstream)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
