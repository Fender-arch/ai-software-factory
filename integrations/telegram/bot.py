"""Telegram bot stub.

Run (optional):
  python -m integrations.telegram.bot

Requires TELEGRAM_BOT_TOKEN. Voice messages go through STT then the same
ingest path as text. Owner HITL: /review /approve /changes /reject /plan /export /mvp /queue /answer /secret.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
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
from core.planner import PlannerError
from core.factory import FactoryError
from core.hitl import HitlAction, HitlError
from core.services import (
    create_project,
    create_project_mvp_job,
    export_project_tasks,
    get_owner_review,
    get_project_mvp,
    ingest_text_message,
    ingest_voice_message,
    list_project_interventions,
    resolve_project_intervention,
    run_project_planner,
    send_project_mvp_to_client,
    submit_hitl_decision,
)

logger = logging.getLogger(__name__)

# Simple in-memory map chat -> project (stub; production will use DB)
_CHAT_PROJECT: dict[int, str] = {}
# Owner is answering an intervention with the next message (no plaintext logs).
_PENDING_INTERVENTION: dict[int, str] = {}


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
        "Владелец: /review · /approve · /changes · /reject · /plan · /export · "
        "/mvp · /queue · /answer · /secret · /sendreview"
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


async def cmd_mvp(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Использование: /mvp <project_id>")
        return
    try:
        with _session() as db:
            snap = create_project_mvp_job(
                db, project_id, actor_telegram_id=_actor_id(message)
            )
    except (ValueError, FactoryError, HitlError) as exc:
        await message.answer(f"Не удалось создать MVP: {exc}")
        return
    _CHAT_PROJECT[message.chat.id] = str(snap["project_id"])
    job = snap.get("job") or {}
    open_iv = [i for i in snap.get("interventions") or [] if i.get("status") == "open"]
    lines = [
        snap.get("message") or "BuildJob создан.",
        f"Статус сборки: `{job.get('status')}`",
        f"Исполнитель: `{job.get('executor')}`",
    ]
    if job.get("deep_link"):
        lines.append(f"Brief/export: {job['deep_link']}")
    if open_iv:
        lines.append(f"Открытых вопросов: {len(open_iv)}. Смотрите /queue")
    await message.answer("\n".join(lines), parse_mode="Markdown")


async def cmd_queue(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Использование: /queue <project_id>")
        return
    try:
        with _session() as db:
            items = list_project_interventions(db, project_id, status="open")
            snap = get_project_mvp(db, project_id)
    except ValueError:
        await message.answer("Проект не найден.")
        return
    job = (snap.get("job") or {}) if snap else {}
    if not items:
        status = job.get("status") or "нет BuildJob"
        await message.answer(f"Открытых вмешательств нет. Сборка: `{status}`", parse_mode="Markdown")
        return
    lines = [f"Intervention Queue — {len(items)}"]
    for item in items:
        cmd = "/secret" if item.get("answer_type") == "secret" else "/answer"
        lines.append(
            f"• {item.get('kind_label')}: {item.get('question')}\n"
            f"  {cmd} `{item['id']}` <значение>"
        )
    await message.answer("\n".join(lines), parse_mode="Markdown")


def _split_intervention_args(command: CommandObject) -> tuple[str | None, str | None]:
    raw = (command.args or "").strip()
    if not raw:
        return None, None
    parts = raw.split(maxsplit=1)
    iid = parts[0]
    answer = parts[1].strip() if len(parts) > 1 else None
    return iid, answer


async def _apply_intervention_answer(
    message: Message, intervention_id: str, answer: str, *, secret: bool
) -> None:
    try:
        with _session() as db:
            snap = resolve_project_intervention(
                db,
                intervention_id,
                answer,
                actor_telegram_id=_actor_id(message),
            )
    except (ValueError, FactoryError, HitlError) as exc:
        await message.answer(f"Не принял ответ: {exc}")
        return
    if secret:
        try:
            await message.delete()
        except Exception:  # noqa: BLE001 — private chats may forbid delete
            logger.info("Could not delete secret reply message")
        confirm = "Секрет принят. Значение не сохранено в ТЗ и не повторяется здесь."
    else:
        confirm = "Ответ принят."
    job = snap.get("job") or {}
    extra = snap.get("message") or ""
    await message.answer(
        f"{confirm}\n{extra}\nСтатус сборки: `{job.get('status')}`",
        parse_mode="Markdown",
    )


async def cmd_answer(message: Message, command: CommandObject) -> None:
    iid, answer = _split_intervention_args(command)
    if not iid:
        await message.answer("Использование: /answer <intervention_id> <текст>")
        return
    if not answer:
        _PENDING_INTERVENTION[message.chat.id] = iid
        await message.answer("Пришлите текст следующим сообщением.")
        return
    await _apply_intervention_answer(message, iid, answer, secret=False)


async def cmd_secret(message: Message, command: CommandObject) -> None:
    iid, answer = _split_intervention_args(command)
    if not iid:
        await message.answer("Использование: /secret <intervention_id> <значение>")
        return
    if not answer:
        _PENDING_INTERVENTION[message.chat.id] = iid
        await message.answer(
            "Пришлите секрет следующим сообщением. "
            "Он не будет повторён в чате и не попадёт в ТЗ."
        )
        return
    await _apply_intervention_answer(message, iid, answer, secret=True)


async def cmd_sendreview(message: Message, command: CommandObject) -> None:
    project_id = _resolve_project_id(message, command)
    if not project_id:
        await message.answer("Использование: /sendreview <project_id>")
        return
    try:
        with _session() as db:
            snap = send_project_mvp_to_client(
                db, project_id, actor_telegram_id=_actor_id(message)
            )
    except (ValueError, FactoryError, HitlError) as exc:
        await message.answer(f"Не отправил клиенту: {exc}")
        return
    await message.answer(snap.get("message") or "Отправлено.")


async def on_intervention_callback(query: CallbackQuery) -> None:
    data = (query.data or "").strip()
    if not data.startswith("iva:"):
        await query.answer()
        return
    iid = data[4:].strip()
    if not iid:
        await query.answer()
        return
    _PENDING_INTERVENTION[query.message.chat.id if query.message else 0] = iid
    await query.answer("Жду ответ следующим сообщением")
    if query.message:
        await query.message.answer(
            "Пришлите ответ следующим сообщением. "
            "Секреты не повторяются в чате и не пишутся в ТЗ."
        )


async def on_text(message: Message) -> None:
    pending = _PENDING_INTERVENTION.pop(message.chat.id, None)
    if pending:
        text = message.text or ""
        secret = True
        try:
            with _session() as db:
                row = None
                from core.factory import get_intervention

                row = get_intervention(db, pending)
                secret = bool(row and row.answer_type == "secret")
        except Exception:  # noqa: BLE001
            secret = True
        await _apply_intervention_answer(message, pending, text, secret=secret)
        return
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
    dp.message.register(cmd_mvp, Command("mvp"))
    dp.message.register(cmd_queue, Command("queue"))
    dp.message.register(cmd_answer, Command("answer"))
    dp.message.register(cmd_secret, Command("secret"))
    dp.message.register(cmd_sendreview, Command("sendreview"))
    dp.callback_query.register(on_intervention_callback, F.data.startswith("iva:"))
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
