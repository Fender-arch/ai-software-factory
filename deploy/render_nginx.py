#!/usr/bin/env python3
"""Render nginx server blocks for ASF domains (never default_server)."""

from __future__ import annotations

from pathlib import Path

HTTP_TEMPLATE = """\
# Managed by ASF deploy. Do not mark as default_server.
# Existing websites on this host are left untouched.
server {{
    listen 80;
    listen [::]:80;
    server_name {server_name};

    client_max_body_size 25m;
    add_header Permissions-Policy "microphone=(self)" always;
    add_header Feature-Policy "microphone 'self'" always;

    location /.well-known/acme-challenge/ {{
        root {acme_root};
        default_type "text/plain";
    }}

    location / {{
        proxy_pass http://{upstream};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Console-Token $http_x_console_token;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}
}}
"""

TLS_TEMPLATE = """\
# Managed by ASF deploy. Do not mark as default_server.
# Existing websites on this host are left untouched.
server {{
    listen 80;
    listen [::]:80;
    server_name {server_name};

    location /.well-known/acme-challenge/ {{
        root {acme_root};
        default_type "text/plain";
    }}

    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {server_name};

    ssl_certificate {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:ASFSSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 25m;
    add_header Permissions-Policy "microphone=(self)" always;
    add_header Feature-Policy "microphone 'self'" always;

    location / {{
        proxy_pass http://{upstream};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Console-Token $http_x_console_token;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }}
}}
"""

DEFAULT_ACME_ROOT = "/var/www/asf-acme"


def normalize_domain(domain: str) -> str:
    host = (domain or "").strip().rstrip("/")
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.split("/", 1)[0].lower()


def letsencrypt_live_dir(server_name: str) -> str:
    return f"/etc/letsencrypt/live/{normalize_domain(server_name)}"


def render_server_block(
    server_name: str,
    upstream: str = "127.0.0.1:18000",
    *,
    tls: bool = False,
    acme_root: str = DEFAULT_ACME_ROOT,
) -> str:
    name = normalize_domain(server_name)
    if not name:
        raise ValueError("server_name is required")
    if "default_server" in name:
        raise ValueError("refusing to emit default_server")
    template = TLS_TEMPLATE if tls else HTTP_TEMPLATE
    return template.format(
        server_name=name,
        upstream=upstream,
        acme_root=acme_root.rstrip("/"),
        cert_dir=letsencrypt_live_dir(name),
    )


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
    *,
    tls_domains: set[str] | None = None,
    acme_root: str = DEFAULT_ACME_ROOT,
) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    tls_domains = {normalize_domain(d) for d in (tls_domains or set())}
    written: list[Path] = []
    for filename, server_name in site_filenames(miniapp_domain, console_domain).items():
        path = dest_dir / filename
        path.write_text(
            render_server_block(
                server_name,
                upstream,
                tls=server_name in tls_domains,
                acme_root=acme_root,
            ),
            encoding="utf-8",
        )
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
    tls_raw = os.environ.get("ASF_TLS_DOMAINS") or ""
    tls_domains = {normalize_domain(p) for p in tls_raw.split(",") if p.strip()}
    paths = write_sites(
        dest,
        mini,
        console,
        upstream,
        tls_domains=tls_domains,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
