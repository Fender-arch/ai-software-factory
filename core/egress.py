"""Outbound HTTP(S) proxy for AI + Telegram (same hop).

Groq / OpenAI / STT clients use vanilla httpx (`trust_env=True`), so they already
honor HTTPS_PROXY / HTTP_PROXY / ALL_PROXY when those are in the process env.
Telegram must resolve the URL explicitly: a custom IPv4 HTTPTransport would
otherwise skip env proxies.

Never log the URL — it may contain credentials.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

PLACEHOLDER = "SET_ME"

# Telegram override first, then the same env httpx AI clients already read,
# then an optional LLM-only alias (not used in-repo today).
OUTBOUND_PROXY_KEYS = (
    "TELEGRAM_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
    "LLM_HTTP_PROXY",
)


def clean_proxy_url(value: str | None) -> str:
    text = (value or "").strip()
    if not text or text == PLACEHOLDER:
        return ""
    return text


def resolve_outbound_proxy_url(
    environ: Mapping[str, str] | None = None,
    *fallbacks: Mapping[str, str] | None,
) -> str:
    """Return the first non-empty proxy URL.

    Order per source: TELEGRAM_PROXY → HTTPS_PROXY → HTTP_PROXY → ALL_PROXY
    → LLM_HTTP_PROXY. Extra mappings are later sources (e.g. existing VPS .env).
    """
    sources: list[Mapping[str, str]] = [
        environ if environ is not None else os.environ
    ]
    for extra in fallbacks:
        if extra:
            sources.append(extra)
    for src in sources:
        for key in OUTBOUND_PROXY_KEYS:
            found = clean_proxy_url(src.get(key))
            if found:
                return found
    return ""


def parse_env_file_values(text: str) -> dict[str, str]:
    """Minimal KEY=value parser (no shell expansion). Does not print values."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        key = key.strip()
        if not key:
            continue
        val = raw.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = (
                val[1:-1]
                .replace("\\n", "\n")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )
        values[key] = val
    return values


def existing_proxy_values(path: Path | None = None) -> dict[str, str]:
    """Proxy keys already on the VPS `.env` (AI channel). Empty if missing."""
    target = path or Path(os.environ.get("ASF_ENV_PATH") or ".env")
    if not target.is_file():
        return {}
    try:
        parsed = parse_env_file_values(target.read_text(encoding="utf-8"))
    except OSError:
        return {}
    return {
        key: value
        for key in OUTBOUND_PROXY_KEYS
        if (value := clean_proxy_url(parsed.get(key)))
    }
