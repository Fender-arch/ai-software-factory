"""Telegram bot stub.

Run (optional):
  python -m integrations.telegram.bot

Requires TELEGRAM_BOT_TOKEN. Voice messages go through STT then the same
ingest path as text.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from core.config import get_settings
from core.db import SessionLocal
from core.services import create_project, ingest_text_message, ingest_voice_message

logger = logging.getLogger(__name__)


def _session():
    return SessionLocal()


async def cmd_start(message: Message) -> None:
    await message.answer(
        "ASF bot ready.\n"
        "Create a project: /new Project Name\n"
        "Then send text or voice in that chat (attach project via /use <id>)."
    )


# Simple in-memory map chat -> project (stub; production will use DB)
_CHAT_PROJECT: dict[int, str] = {}


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
    await message.answer(f"Project created: {name}\nID: `{project_id}`", parse_mode="Markdown")


async def cmd_use(message: Message, command: CommandObject) -> None:
    project_id = (command.args or "").strip()
    if not project_id:
        await message.answer("Usage: /use <project_id>")
        return
    _CHAT_PROJECT[message.chat.id] = project_id
    await message.answer(f"Active project: `{project_id}`", parse_mode="Markdown")


async def on_text(message: Message) -> None:
    project_id = _CHAT_PROJECT.get(message.chat.id)
    if not project_id:
        await message.answer("Create a project first: /new My Project")
        return
    with _session() as db:
        ingest_text_message(db, project_id=project_id, text=message.text or "")
    await message.answer("Saved. Discovery LLM will continue in a later epic.")


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
        msg = await ingest_voice_message(
            db,
            project_id=project_id,
            audio=audio,
            telegram_file_id=message.voice.file_id,
        )
    await message.answer(f"Voice saved as text:\n{msg.text}")


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
    dp.message.register(on_voice, F.voice)
    dp.message.register(on_text, F.text)

    logger.info("Starting ASF Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
