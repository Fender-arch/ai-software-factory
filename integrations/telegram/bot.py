"""Telegram bot stub.

Run (optional):
  python -m integrations.telegram.bot

Requires TELEGRAM_BOT_TOKEN. Voice messages go through STT then the same
ingest path as text. Owner HITL: /review /approve /changes /reject /plan /export.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from core.config import get_settings
from core.db import SessionLocal
from core.estimate import format_estimate_review_block
from core.export import ExportError
from core.hitl import HitlAction, HitlError
from core.planner import PlannerError
from core.services import (
    create_project,
    export_project_tasks,
    get_owner_review,
    ingest_text_message,
    ingest_voice_message,
    run_project_planner,
    submit_hitl_decision,
)

logger = logging.getLogger(__name__)

# Simple in-memory map chat -> project (stub; production will use DB)
_CHAT_PROJECT: dict[int, str] = {}


def _session():
    return SessionLocal()


def _actor_id(message: Message) -> str:
    return str(message.from_user.id if message.from_user else "")


def _resolve_project_id(message: Message, command: CommandObject) -> str | None:
    args = (command.args or "").strip().split()
    if args:
        return args[0]
    return _CHAT_PROJECT.get(message.chat.id)


def _note_from_args(command: CommandObject) -> str | None:
    parts = (command.args or "").strip().split(maxsplit=1)
    if len(parts) >= 2:
        return parts[1].strip() or None
    return None


async def cmd_start(message: Message) -> None:
    settings = get_settings()
    text = (
        "ASF — AI Software Factory.\n\n"
        "Кратко: вы описываете идею → мы собираем требования (Discovery) → "
        "готовим черновик ТЗ → владелец ревьюит → задачи для простого MVP.\n\n"
        "Основной интерфейс — Mini App (кнопка ниже или меню бота):\n"
        "• Создать проект\n"
        "• Изменить проект\n"
        "• Замечания к реализации\n\n"
        "Пока Mini App недоступен, можно временно: /new Название · /use <id> · текст/голос.\n"
        "Владелец: /review · /approve · /changes · /reject · /plan · /export"
    )
    url = (settings.miniapp_url or "").strip()
    if url:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Открыть ASF",
                        web_app=WebAppInfo(url=url),
                    )
                ]
            ]
        )
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(
            text
            + "\n\n_Подсказка: задайте MINIAPP_URL (HTTPS) в .env, чтобы открыть Mini App._",
            parse_mode="Markdown",
        )


async def cmd_new(message: Message, command: CommandObject) -> None:
    name = (command.args or "").strip() or f"project-{message.chat.id}"
    with _session() as db:
        project = create_project(
            db,
            name=name,
            customer_telegram_id=str(message.from_user.id if message.from_user else ""),
        )
        project_id = str(project.id)
    _CHAT_PROJECT[message.chat.id] = project_id
    await message.answer(
        f"Проект создан: {name}\nID: `{project_id}`\n"
        "Лучше продолжить в Mini App (кнопка «Открыть ASF» или меню бота).",
        parse_mode="Markdown",
    )


async def cmd_use(message: Message, command: CommandObject) -> None:
    project_id = (command.args or "").strip()
    if not project_id:
        await message.answer("Использование: /use <project_id>")
        return
    _CHAT_PROJECT[message.chat.id] = project_id
    await message.answer(f"Active project: `{project_id}`", parse_mode="Markdown")


async def cmd_review(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Usage: /review <project_id>")
        return
    try:
        with _session() as db:
            summary = get_owner_review(db, project_id)
    except ValueError:
        await message.answer("Project not found.")
        return

    gaps = "\n".join(f"• {q}" for q in summary.get("open_questions") or []) or "• none"
    preview = summary.get("draft_preview") or "_no draft TZ_"
    estimate_block = format_estimate_review_block(summary.get("estimate"))
    estimate_section = f"{estimate_block}\n\n" if estimate_block else ""
    text = (
        f"HITL review — {summary['name']}\n"
        f"Status: `{summary['status']}` · type: `{summary.get('product_type')}`\n"
        f"Artifact: `{summary.get('artifact_id')}` ({summary.get('artifact_status')})\n\n"
        f"{estimate_section}"
        f"Open questions:\n{gaps}\n\n"
        f"Draft preview:\n{preview}\n\n"
        f"/approve {summary['project_id']}\n"
        f"/changes {summary['project_id']} <note>\n"
        f"/reject {summary['project_id']} <note>"
    )
    await message.answer(text, parse_mode="Markdown")


async def cmd_approve(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Usage: /approve <project_id>")
        return
    try:
        with _session() as db:
            result = submit_hitl_decision(
                db,
                project_id,
                HitlAction.APPROVE,
                actor_telegram_id=_actor_id(message),
            )
    except (ValueError, HitlError) as exc:
        await message.answer(f"HITL failed: {exc}")
        return
    _CHAT_PROJECT[message.chat.id] = str(result.project_id)
    await message.answer(
        f"{result.message}\nStatus: `{result.project_status.value}`\n"
        f"Next: /plan `{result.project_id}`",
        parse_mode="Markdown",
    )


async def cmd_changes(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Usage: /changes <project_id> <reason>")
        return
    note = _note_from_args(command)
    try:
        with _session() as db:
            result = submit_hitl_decision(
                db,
                project_id,
                HitlAction.REQUEST_CHANGES,
                note=note,
                actor_telegram_id=_actor_id(message),
            )
    except (ValueError, HitlError) as exc:
        await message.answer(f"HITL failed: {exc}")
        return
    await message.answer(
        f"{result.message}\nStatus: `{result.project_status.value}`",
        parse_mode="Markdown",
    )


async def cmd_reject(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Usage: /reject <project_id> <reason>")
        return
    note = _note_from_args(command)
    try:
        with _session() as db:
            result = submit_hitl_decision(
                db,
                project_id,
                HitlAction.REJECT,
                note=note,
                actor_telegram_id=_actor_id(message),
            )
    except (ValueError, HitlError) as exc:
        await message.answer(f"HITL failed: {exc}")
        return
    await message.answer(
        f"{result.message}\nStatus: `{result.project_status.value}`",
        parse_mode="Markdown",
    )


async def cmd_plan(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Usage: /plan <project_id>")
        return
    try:
        with _session() as db:
            result = await run_project_planner(db, project_id)
    except (ValueError, PlannerError) as exc:
        await message.answer(f"Planner failed: {exc}")
        return
    tasks = result["output"]["tasks"]
    lines = [f"Planner: {len(tasks)} task(s)"]
    for i, t in enumerate(tasks, start=1):
        lines.append(f"{i}. {t['title']} (`{t['id']}`)")
    lines.append(f"\nExport: /export `{project_id}`")
    await message.answer("\n".join(lines), parse_mode="Markdown")


async def cmd_export(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Usage: /export <project_id>")
        return
    try:
        with _session() as db:
            exported = export_project_tasks(db, project_id, format="markdown")
    except (ValueError, ExportError) as exc:
        await message.answer(f"Export failed: {exc}")
        return
    # Telegram message limit ~4096; send head + tip for full API export
    body = exported.content
    if len(body) > 3500:
        body = body[:3500] + "\n\n…truncated. Full export: GET /projects/{id}/export/tasks"
    await message.answer(body)


async def on_text(message: Message) -> None:
    project_id = _CHAT_PROJECT.get(message.chat.id)
    if not project_id:
        await message.answer("Create a project first: /new My Project")
        return
    with _session() as db:
        result = ingest_text_message(
            db, project_id=project_id, text=message.text or ""
        )
    reply = (
        result.discovery.reply_to_customer
        if result.discovery
        else "Saved."
    )
    if result.discovery and result.discovery.project_status.value == "WAITING_OWNER":
        reply += (
            f"\n\nOwner: /review `{project_id}` then /approve or /changes."
        )
    await message.answer(reply, parse_mode="Markdown")


async def on_voice(message: Message, bot: Bot) -> None:
    project_id = _CHAT_PROJECT.get(message.chat.id)
    if not project_id:
        await message.answer("Create a project first: /new My Project")
        return
    if not message.voice:
        return
    file = await bot.get_file(message.voice.file_id)
    raw = await bot.download_file(file.file_path)
    audio = raw.read() if hasattr(raw, "read") else bytes(raw)
    with _session() as db:
        result = await ingest_voice_message(
            db,
            project_id=project_id,
            audio=audio,
            telegram_file_id=message.voice.file_id,
        )
    transcript = result.message.text
    reply = (
        result.discovery.reply_to_customer
        if result.discovery
        else "Voice saved."
    )
    if result.discovery and result.discovery.project_status.value == "WAITING_OWNER":
        reply += f"\n\nOwner: /review `{project_id}`"
    await message.answer(f"Heard:\n{transcript}\n\n{reply}", parse_mode="Markdown")


async def run_bot() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is empty")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_new, Command("new"))
    dp.message.register(cmd_use, Command("use"))
    dp.message.register(cmd_review, Command("review"))
    dp.message.register(cmd_approve, Command("approve"))
    dp.message.register(cmd_changes, Command("changes"))
    dp.message.register(cmd_reject, Command("reject"))
    dp.message.register(cmd_plan, Command("plan"))
    dp.message.register(cmd_export, Command("export"))
    dp.message.register(on_voice, F.voice)
    dp.message.register(on_text, F.text)

    url = (settings.miniapp_url or "").strip()
    if url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="ASF",
                    web_app=WebAppInfo(url=url),
                )
            )
        except Exception:  # noqa: BLE001 — menu button is best-effort
            logger.exception("Failed to set Mini App menu button")

    logger.info("Starting ASF Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
