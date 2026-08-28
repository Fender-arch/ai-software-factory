"""Owner Telegram notifications (sync HTTP, usable from API and bot)."""

from __future__ import annotations

import logging

import httpx

from core.config import get_settings
from core.estimate import DeliveryEstimate, format_owner_draft_ready_message
from core.models import Project

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT_S = 5.0


def send_owner_telegram(text: str, *, parse_mode: str | None = "Markdown") -> bool:
    """Send a DM to OWNER_TELEGRAM_ID. Returns False if skipped or send failed."""
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    owner = (settings.owner_telegram_id or "").strip()
    if not token or not owner:
        return False
    payload: dict[str, str] = {"chat_id": owner, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        with httpx.Client(timeout=_TIMEOUT_S) as client:
            response = client.post(
                _TELEGRAM_API.format(token=token),
                json=payload,
            )
            response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — notify must not break Discovery/HITL
        logger.exception("Failed to send owner Telegram message")
        return False


def notify_owner_draft_ready(
    project: Project,
    estimate: DeliveryEstimate,
) -> bool:
    text = format_owner_draft_ready_message(
        name=project.name,
        project_id=str(project.id),
        estimate=estimate,
    )
    return send_owner_telegram(text)


def send_customer_telegram_document(
    chat_id: str,
    *,
    data: bytes,
    filename: str,
    caption: str | None = None,
) -> bool:
    """Send a file to the customer's Telegram chat. False if skipped or failed."""
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    dest = (chat_id or "").strip()
    if not token or not dest or not data:
        return False
    payload: dict[str, str] = {"chat_id": dest}
    if caption:
        payload["caption"] = caption[:1024]
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data=payload,
                files={"document": (filename, data)},
            )
            response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — customer download must not crash Mini App
        logger.exception("Failed to send customer Telegram document")
        return False
