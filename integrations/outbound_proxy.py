"""Optional outbound HTTP proxy (VPS geo egress tunnel)."""

from __future__ import annotations

import os


_PROXY_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "ALL_PROXY",
    "all_proxy",
)


def http_proxy_url(environ: dict[str, str] | None = None) -> str | None:
    """Return the first non-empty proxy URL from standard env vars."""
    src = environ if environ is not None else os.environ
    for key in _PROXY_KEYS:
        value = (src.get(key) or "").strip()
        if value:
            return value
    return None
