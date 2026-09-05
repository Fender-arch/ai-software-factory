"""Owner Telegram notifications (sync HTTP, usable from API and bot)."""

from __future__ import annotations

import logging
import os
import socket

import httpx

from core.config import get_settings
from core.client_estimate import (
    ClientEstimate,
    ClientEstimateAction,
    format_client_estimate_ready_message,
    format_owner_client_decision_message,
    format_owner_client_estimate_ready_message,
)
from core.estimate import DeliveryEstimate, format_owner_draft_ready_message
from core.models import Project

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_TELEGRAM_ORIGIN = "https://api.telegram.org"
_TIMEOUT_S = 5.0

# Stable codes — Mini App / services map these; never put the bot token here.
TELEGRAM_UNREACHABLE = "telegram_bot_api_unreachable"
MSG_TELEGRAM_UNREACHABLE = (
    "Сервер не смог связаться с Telegram Bot API (не ваш интернет). Попробуйте ещё раз."
)
MSG_TELEGRAM_START_REQUIRED = "Напишите боту /start в личке и нажмите снова"
MSG_TELEGRAM_BAD_TOKEN = "бот на сервере настроен неверно"


def _has_ipv4_default_route() -> bool:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(1)
        probe.connect(("1.1.1.1", 443))
        probe.close()
        return True
    except OSError:
        return False


def telegram_http_client(timeout: float) -> httpx.Client:
    """HTTP client for api.telegram.org.

    Dual-stack Docker often resolves AAAA first and then ConnectError (no IPv6
    NAT). Prefer IPv4 when the box has an IPv4 route. Respects HTTPS_PROXY /
    HTTP_PROXY from the environment (trust_env). Never logs the bot token.
    """
    mode = (os.environ.get("ASF_TELEGRAM_IP") or "auto").strip().lower()
    kwargs: dict = {"timeout": timeout, "trust_env": True}
    if mode == "4" or (mode != "6" and _has_ipv4_default_route()):
        kwargs["transport"] = httpx.HTTPTransport(local_address="0.0.0.0")
    return httpx.Client(**kwargs)


def send_owner_telegram(
    text: str,
    *,
    parse_mode: str | None = "Markdown",
    reply_markup: dict | None = None,
) -> bool:
    """Send a DM to OWNER_TELEGRAM_ID. Returns False if skipped or send failed."""
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    owner = (settings.owner_telegram_id or "").strip()
    if not token or not owner:
        return False
    payload: dict = {"chat_id": owner, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        with telegram_http_client(_TIMEOUT_S) as client:
            response = client.post(
                _TELEGRAM_API.format(token=token),
                json=payload,
            )
            response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — notify must not break Discovery/HITL
        logger.exception("Failed to send owner Telegram message")
        return False


def send_customer_telegram(chat_id: str, text: str) -> bool:
    """Plain-text DM to a customer chat. False if skipped or failed."""
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    dest = (chat_id or "").strip()
    if not token or not dest or not (text or "").strip():
        return False
    try:
        with telegram_http_client(_TIMEOUT_S) as client:
            response = client.post(
                _TELEGRAM_API.format(token=token),
                json={"chat_id": dest, "text": text},
            )
            response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send customer Telegram message")
        return False


def notify_owner_interventions(project, interventions: list[dict]) -> bool:
    """RU questions for the Intervention Queue. No secrets in the text."""
    if not interventions:
        return False
    sent = False
    for item in interventions:
        kind = item.get("kind_label") or item.get("kind") or "вопрос"
        answer_type = item.get("answer_type") or "text"
        type_ru = "секрет" if answer_type == "secret" else "текст"
        expires = item.get("ttl_expires_at") or "—"
        cmd = "/secret" if answer_type == "secret" else "/answer"
        iid = item.get("id") or ""
        text = (
            f"Нужно ваше решение — Intervention Queue\n\n"
            f"Проект: {project.name}\n"
            f"Что: {kind} ({type_ru})\n\n"
            f"{item.get('question') or ''}\n\n"
            f"Ответьте в боте:\n{cmd} {iid} <значение>\n"
            f"или нажмите «Ответить» и пришлите следующим сообщением.\n"
            f"Секреты не пишутся в ТЗ и в граф знаний.\n"
            f"Срок: {expires}"
        )
        markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "Ответить",
                        "callback_data": f"iva:{iid}",
                    }
                ]
            ]
        }
        sent = send_owner_telegram(text, parse_mode=None, reply_markup=markup) or sent
    return sent


def notify_customer_mvp_review(project, job) -> bool:
    chat = (project.customer_telegram_id or "").strip()
    text = (
        f"MVP по проекту «{project.name}» готов и отправлен вам на review.\n"
        "Откройте Mini App → «Замечания к реализации», если нужно что-то поправить."
    )
    return send_customer_telegram(chat, text)


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


def send_telegram_text(
    chat_id: str,
    text: str,
    *,
    parse_mode: str | None = "Markdown",
) -> bool:
    """Send a Telegram text message to any chat. False if skipped or failed."""
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    dest = (chat_id or "").strip()
    if not token or not dest or not text:
        return False
    payload: dict[str, str] = {"chat_id": dest, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        with telegram_http_client(_TIMEOUT_S) as client:
            response = client.post(
                _TELEGRAM_API.format(token=token),
                json=payload,
            )
            response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — notify must not break HITL / Mini App
        logger.exception("Failed to send Telegram message to %s", dest)
        return False


def send_customer_telegram(chat_id: str, text: str) -> bool:
    return send_telegram_text(chat_id, text, parse_mode=None)


def notify_customer_client_estimate_ready(
    project: Project,
    estimate: ClientEstimate,
) -> bool:
    chat_id = (project.customer_telegram_id or "").strip()
    if not chat_id:
        return False
    return send_customer_telegram(
        chat_id,
        format_client_estimate_ready_message(name=project.name, estimate=estimate),
    )


def notify_owner_client_estimate_ready(
    project: Project,
    estimate: ClientEstimate,
) -> bool:
    return send_owner_telegram(
        format_owner_client_estimate_ready_message(
            name=project.name,
            project_id=str(project.id),
            estimate=estimate,
        )
    )


def notify_owner_client_estimate_decision(
    project: Project,
    action: ClientEstimateAction,
    estimate: ClientEstimate | None,
) -> bool:
    return send_owner_telegram(
        format_owner_client_decision_message(
            name=project.name,
            project_id=str(project.id),
            action=action,
            estimate=estimate,
        )
    )


def _private_user_chat_id(raw: str | int | None) -> str | None:
    """Positive Telegram user id for a private DM. Groups/channels are negative."""
    text = str(raw or "").strip()
    if not text or text.startswith("@"):
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return str(value)


def customer_dm_chat_id(
    *,
    project_customer_telegram_id: str | None,
    actor_telegram_id: str | None,
    owner_telegram_id: str | None = None,
) -> str | None:
    """Customer↔bot DM id. Actor (Mini App user) wins; never owner fallback."""
    del owner_telegram_id  # explicit: OWNER_TELEGRAM_ID is not a destination
    return _private_user_chat_id(actor_telegram_id) or _private_user_chat_id(
        project_customer_telegram_id
    )


def _telegram_upload_filename(filename: str) -> tuple[str, str]:
    """ASCII name + MIME. Telegram/httpx break on Cyrillic filename* headers."""
    lower = (filename or "tz.md").lower()
    if lower.endswith(".pdf"):
        ext, mime = "pdf", "application/pdf"
    elif lower.endswith(".docx"):
        ext, mime = (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    else:
        ext, mime = "md", "text/markdown"
    kind = "smeta" if "smeta" in lower else "tz"
    return f"{kind}.{ext}", mime


_bot_identity: dict | None = None


def reset_telegram_identity_cache() -> None:
    global _bot_identity
    _bot_identity = None


def probe_telegram_bot_api() -> dict:
    """VPS egress to api.telegram.org (no bot token). Used by deploy/ops."""
    try:
        with telegram_http_client(_TIMEOUT_S) as client:
            response = client.get(_TELEGRAM_ORIGIN)
        return {"ok": True, "http_status": response.status_code, "error": None}
    except httpx.RequestError as exc:
        logger.warning(
            "Telegram Bot API egress probe failed error=%s",
            type(exc).__name__,
        )
        return {"ok": False, "http_status": None, "error": type(exc).__name__}


def diagnose_telegram_bot_api() -> dict:
    """Egress + getMe. Never returns or logs the bot token / token URL."""
    egress = probe_telegram_bot_api()
    result = {
        "egress_ok": bool(egress.get("ok")),
        "egress_http_status": egress.get("http_status"),
        "egress_error": egress.get("error"),
        "bot_ok": False,
        "bot_username": None,
        "bot_http_status": None,
        "bot_description": None,
    }
    token = (get_settings().telegram_bot_token or "").strip()
    if not token or token == "SET_ME":
        result["bot_description"] = "token_missing"
        return result
    try:
        with telegram_http_client(_TIMEOUT_S) as client:
            response = client.post(f"{_TELEGRAM_ORIGIN}/bot{token}/getMe")
    except httpx.RequestError as exc:
        logger.warning("Telegram getMe transport failed error=%s", type(exc).__name__)
        result["bot_description"] = type(exc).__name__
        return result
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        result["bot_http_status"] = response.status_code
        result["bot_description"] = "non_json"
        return result
    result["bot_http_status"] = response.status_code
    if isinstance(body, dict) and body.get("ok"):
        username = str((body.get("result") or {}).get("username") or "").strip() or None
        result["bot_ok"] = True
        result["bot_username"] = username
        return result
    desc = (
        (body.get("description") if isinstance(body, dict) else None) or "getMe_failed"
    )
    result["bot_description"] = desc
    logger.warning(
        "Telegram getMe rejected http=%s description=%s",
        response.status_code,
        desc,
    )
    return result


def classify_telegram_document_error(
    description: str,
    *,
    error_kind: str | None = None,
    http_status: int | None = None,
) -> str:
    """Russian Mini App copy. Never mention the user's Telegram network."""
    low = (description or "").lower()
    kind = (error_kind or "").lower()
    if (
        kind == "transport"
        or TELEGRAM_UNREACHABLE in low
        or "сеть до telegram недоступна" in low
    ):
        return MSG_TELEGRAM_UNREACHABLE
    if (
        kind == "unauthorized"
        or http_status == 401
        or "unauthorized" in low
        or "invalid token" in low
        or "token_missing" in low
        or "бот не настроен" in low
    ):
        return MSG_TELEGRAM_BAD_TOKEN
    if kind == "start_required" or any(
        token in low
        for token in (
            "can't initiate",
            "cannot initiate",
            "chat not found",
            "bot was blocked",
            "forbidden",
            "have no access",
        )
    ):
        return MSG_TELEGRAM_START_REQUIRED
    return description or "не удалось отправить файл в чат бота"


def telegram_bot_username() -> str | None:
    """Cached @username from getMe. Never logs token or API URL."""
    global _bot_identity
    if _bot_identity is not None:
        return _bot_identity.get("username")
    token = (get_settings().telegram_bot_token or "").strip()
    if not token:
        _bot_identity = {}
        return None
    try:
        with telegram_http_client(_TIMEOUT_S) as client:
            response = client.post(f"{_TELEGRAM_ORIGIN}/bot{token}/getMe")
        body = response.json()
    except Exception as exc:  # noqa: BLE001 — identity is optional for send
        logger.warning("Telegram getMe failed error=%s", type(exc).__name__)
        _bot_identity = {}
        return None
    if not isinstance(body, dict) or not body.get("ok"):
        logger.warning(
            "Telegram getMe rejected http=%s description=%s",
            response.status_code,
            body.get("description") if isinstance(body, dict) else None,
        )
        _bot_identity = {}
        return None
    result = body.get("result") or {}
    username = str(result.get("username") or "").strip() or None
    _bot_identity = {"username": username, "id": result.get("id")}
    return username


def send_customer_telegram_document(
    chat_id: str,
    *,
    data: bytes,
    filename: str,
    caption: str | None = None,
) -> dict | None:
    """Send a file to the customer↔bot DM.

    Success only when Telegram JSON has ok=true, message_id, and result.chat.id
    matches the requested private user id. Never logs the bot token or API URL.
    """
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    dest = _private_user_chat_id(chat_id)
    if not token:
        return {
            "ok": False,
            "error_kind": "unauthorized",
            "description": "token_missing",
        }
    if not dest:
        return {
            "ok": False,
            "description": "нет chat_id — откройте Mini App из Telegram и нажмите /start",
        }
    if not data:
        return {"ok": False, "description": "пустой файл"}
    ascii_name, mime = _telegram_upload_filename(filename)
    payload: dict[str, str | int] = {"chat_id": int(dest)}
    if caption:
        payload["caption"] = caption[:1024]
    try:
        with telegram_http_client(30.0) as client:
            response = client.post(
                f"{_TELEGRAM_ORIGIN}/bot{token}/sendDocument",
                data=payload,
                files={"document": (ascii_name, data, mime)},
            )
    except httpx.RequestError as exc:
        logger.warning(
            "Telegram sendDocument transport failed chat_id=%s error=%s",
            dest,
            type(exc).__name__,
        )
        return {
            "ok": False,
            "chat_id": dest,
            "error_kind": "transport",
            "description": TELEGRAM_UNREACHABLE,
        }
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        logger.warning(
            "Telegram sendDocument non-json chat_id=%s http=%s",
            dest,
            response.status_code,
        )
        return {
            "ok": False,
            "chat_id": dest,
            "error_kind": "telegram",
            "http_status": response.status_code,
            "description": f"Telegram вернул не JSON (http={response.status_code})",
        }
    if not isinstance(body, dict) or not body.get("ok"):
        desc = (
            (body.get("description") if isinstance(body, dict) else None)
            or f"Telegram отклонил файл (http={response.status_code})"
        )
        low = desc.lower()
        http_status = response.status_code
        if http_status == 401 or "unauthorized" in low or "invalid token" in low:
            error_kind = "unauthorized"
        elif any(
            token in low
            for token in (
                "can't initiate",
                "cannot initiate",
                "chat not found",
                "bot was blocked",
                "forbidden",
                "have no access",
            )
        ):
            error_kind = "start_required"
        else:
            error_kind = "telegram"
        logger.warning(
            "Telegram sendDocument rejected chat_id=%s http=%s description=%s",
            dest,
            http_status,
            desc,
        )
        return {
            "ok": False,
            "chat_id": dest,
            "error_kind": error_kind,
            "http_status": http_status,
            "description": desc,
        }
    result = body.get("result") or {}
    message_id = result.get("message_id")
    result_chat = _private_user_chat_id((result.get("chat") or {}).get("id"))
    if not message_id or not result_chat:
        logger.warning(
            "Telegram sendDocument missing message_id/chat chat_id=%s http=%s",
            dest,
            response.status_code,
        )
        return {
            "ok": False,
            "chat_id": dest,
            "description": "Telegram не вернул message_id",
        }
    if result_chat != dest:
        logger.warning(
            "Telegram sendDocument chat mismatch requested=%s actual=%s message_id=%s",
            dest,
            result_chat,
            message_id,
        )
        return {
            "ok": False,
            "chat_id": dest,
            "description": "файл ушёл не в чат заказчика",
        }
    username = telegram_bot_username()
    logger.info(
        "Telegram sendDocument ok chat_id=%s message_id=%s bot=%s",
        dest,
        message_id,
        username or "-",
    )
    return {
        "ok": True,
        "chat_id": dest,
        "message_id": int(message_id),
        "bot_username": username,
        "filename": ascii_name,
    }
