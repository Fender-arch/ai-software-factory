"""Documented market rate bands for the client estimate (DEC-012).

Built-in table is the default. Optional HTTPS fetch only hits an allowlist.
Never invent closed-studio labels such as “Admin analytics”.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from urllib.parse import urlparse

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

TABLE_VERSION = "asf_market_table_v1"
TABLE_RETRIEVED = "2026-09-05"
DEFAULT_FX_USD_RUB = 90.0
_FETCH_TIMEOUT_S = 4.0

DISCLAIMER_RU = (
    "Это рыночный ориентир для согласования объёма, не юридическая оферта и не счёт к оплате."
)


def _source(
    *,
    name: str,
    note: str,
    kind: str = "config",
    url: str | None = None,
    retrieved: str = TABLE_RETRIEVED,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "retrieved": retrieved,
        "url": url,
        "note": note,
    }


BUILTIN_BANDS: dict[str, dict[str, Any]] = {
    "ru_cis_freelance": {
        "id": "ru_cis_freelance",
        "label": "Фриланс RU/CIS",
        "currency": "RUB",
        "hourly": {"low": 2000, "mid": 3500, "high": 5500},
        "source": _source(
            name="ASF market table v1 — RU/CIS freelance hourly bands",
            note=(
                "Скомпилированные публичные ориентиры junior–senior для веб/бот/API MVP "
                "(типовые вилки фриланс-бирж и открытых обзоров ставок). "
                "Не закрытая аналитика студии."
            ),
        ),
    },
    "ee_contractor": {
        "id": "ee_contractor",
        "label": "Подрядчики Eastern Europe",
        "currency": "USD",
        "hourly": {"low": 25, "mid": 40, "high": 65},
        "fx_to_rub": DEFAULT_FX_USD_RUB,
        "source": _source(
            name="ASF market table v1 — Eastern Europe contractor bands",
            note=(
                "Ориентиры mid–senior EE в USD по открытым обзорам подрядных ставок. "
                "Перевод в RUB — курс из конфига ASF, не биржевой фид."
            ),
        ),
    },
}


def _copy_band(band: dict[str, Any]) -> dict[str, Any]:
    hourly = dict(band.get("hourly") or {})
    source = dict(band.get("source") or {})
    out = {
        "id": band.get("id"),
        "label": band.get("label"),
        "currency": band.get("currency") or "RUB",
        "hourly": {
            "low": float(hourly.get("low") or 0),
            "mid": float(hourly.get("mid") or 0),
            "high": float(hourly.get("high") or 0),
        },
        "source": source,
    }
    if band.get("fx_to_rub") is not None:
        out["fx_to_rub"] = float(band["fx_to_rub"])
    return out


def builtin_market_table() -> dict[str, Any]:
    return {
        "version": TABLE_VERSION,
        "retrieved": TABLE_RETRIEVED,
        "disclaimer": DISCLAIMER_RU,
        "fx_usd_rub": DEFAULT_FX_USD_RUB,
        "bands": {key: _copy_band(val) for key, val in BUILTIN_BANDS.items()},
        "sources": [dict(val["source"]) for val in BUILTIN_BANDS.values()],
        "fetched": False,
    }


def _host_allowlisted(url: str, allowlist: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or not allowlist:
        return False
    return host in {h.strip().lower() for h in allowlist if h.strip()}


def _parse_remote_table(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    bands_in = raw.get("bands")
    if not isinstance(bands_in, dict) or not bands_in:
        return None
    bands: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for key, val in bands_in.items():
        if not isinstance(val, dict):
            continue
        hourly = val.get("hourly") if isinstance(val.get("hourly"), dict) else {}
        low = hourly.get("low")
        mid = hourly.get("mid")
        high = hourly.get("high")
        try:
            parsed_hourly = {
                "low": float(low),
                "mid": float(mid),
                "high": float(high),
            }
        except (TypeError, ValueError):
            continue
        if min(parsed_hourly.values()) <= 0:
            continue
        src = val.get("source") if isinstance(val.get("source"), dict) else {}
        source = _source(
            name=str(src.get("name") or f"Fetched band {key}"),
            note=str(src.get("note") or "Публичный JSON ориентиров (allowlist fetch)."),
            kind="fetched",
            url=src.get("url"),
            retrieved=str(src.get("retrieved") or date.today().isoformat()),
        )
        band = {
            "id": str(val.get("id") or key),
            "label": str(val.get("label") or key),
            "currency": str(val.get("currency") or "RUB"),
            "hourly": parsed_hourly,
            "source": source,
        }
        if val.get("fx_to_rub") is not None:
            try:
                band["fx_to_rub"] = float(val["fx_to_rub"])
            except (TypeError, ValueError):
                pass
        bands[str(key)] = band
        sources.append(source)
    if not bands:
        return None
    table = builtin_market_table()
    table["bands"].update(bands)
    table["sources"].extend(sources)
    table["fetched"] = True
    if raw.get("disclaimer"):
        table["disclaimer"] = str(raw["disclaimer"])
    return table


def load_market_table(*, fetch: bool = True) -> dict[str, Any]:
    """Return builtin bands, optionally merged with an allowlisted JSON file."""
    table = builtin_market_table()
    if not fetch:
        return table
    settings = get_settings()
    url = (settings.asf_market_rates_url or "").strip()
    if not url:
        return table
    allowlist = [
        part.strip()
        for part in (settings.asf_market_rates_allowlist or "").split(",")
        if part.strip()
    ]
    if not _host_allowlisted(url, allowlist):
        logger.warning("Skipped market-rates fetch: URL host is not allowlisted")
        return table
    try:
        with httpx.Client(timeout=_FETCH_TIMEOUT_S, follow_redirects=False) as client:
            response = client.get(url)
            response.raise_for_status()
            remote = _parse_remote_table(response.json())
    except Exception:  # noqa: BLE001 — fetch is optional; builtin table stays
        logger.exception("Market-rates fetch failed; using builtin table")
        return table
    return remote or table


def primary_band(table: dict[str, Any] | None = None) -> dict[str, Any]:
    data = table or builtin_market_table()
    bands = data.get("bands") or {}
    return _copy_band(bands.get("ru_cis_freelance") or next(iter(bands.values())))


def ee_band(table: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = table or builtin_market_table()
    bands = data.get("bands") or {}
    raw = bands.get("ee_contractor")
    return _copy_band(raw) if raw else None
