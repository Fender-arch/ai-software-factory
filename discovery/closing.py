"""Wrap-up questions after TZ sections (and clarify) are done."""

from __future__ import annotations

from dataclasses import dataclass

from discovery.tz_outline import Choice

CLOSING_ADDITIONS = "closing_additions"
CLOSING_BUDGET = "closing_budget"
CLOSING_BRIEF = "closing_brief"
SOURCE_BRIEF_TOPIC = "source_brief"


@dataclass(frozen=True)
class ClosingItem:
    id: str
    topic_id: str
    title_ru: str
    question: str
    why: str
    options: tuple[Choice, ...]
    needs_substance: bool = False


def closing_catalog() -> tuple[ClosingItem, ...]:
    return (
        ClosingItem(
            id=CLOSING_ADDITIONS,
            topic_id=CLOSING_ADDITIONS,
            title_ru="Есть ли что добавить",
            question=(
                "Разделы ТЗ закрыты. Есть ли ещё что добавить — детали, ограничения, "
                "примеры, ссылки, — чего мы не спросили?"
            ),
            why="Дополнение попадёт в черновик ТЗ, который уйдёт разработчику.",
            needs_substance=True,
            options=(
                Choice("add_none", "Нет, ничего не добавляю"),
                Choice(
                    "add_write",
                    "Сейчас допишу текстом",
                    sufficient=False,
                ),
                Choice(
                    "add_file",
                    "Сейчас прикреплю файл или вставлю текст",
                    sufficient=False,
                ),
            ),
        ),
        ClosingItem(
            id=CLOSING_BUDGET,
            topic_id="budget",
            title_ru="Сумма на первую версию",
            question=(
                "Какую сумму закладываете на первую версию? Можно точную цифру "
                "или уточнить ориентир из интервью."
            ),
            why="Цифра в ТЗ помогает оценить объём; это не замена ревью владельца.",
            needs_substance=True,
            options=(
                Choice("bud_keep", "Оставить ориентир из интервью"),
                Choice(
                    "bud_write",
                    "Сейчас напишу сумму",
                    sufficient=False,
                ),
                Choice("bud_quote", "Сумму не фиксирую — нужна оценка разработчика"),
            ),
        ),
        ClosingItem(
            id=CLOSING_BRIEF,
            topic_id=SOURCE_BRIEF_TOPIC,
            title_ru="Готовая постановка",
            question=(
                "Есть ли уже постановка в файле — например, задание, которое вы "
                "собирали с ChatGPT или другой нейросетью? Можно прикрепить файл "
                "или вставить текст: разберём и добавим в ТЗ."
            ),
            why="Готовый бриф экономит правки и не должен потеряться вне интервью.",
            needs_substance=True,
            options=(
                Choice("brief_none", "Нет готовой постановки"),
                Choice(
                    "brief_paste",
                    "Сейчас вставлю текст из нейросети / документа",
                    sufficient=False,
                ),
                Choice(
                    "brief_file",
                    "Сейчас прикреплю файл постановки",
                    sufficient=False,
                ),
            ),
        ),
    )


def closing_ids() -> list[str]:
    return [item.id for item in closing_catalog()]


def closing_item_by_id(item_id: str | None) -> ClosingItem | None:
    if not item_id:
        return None
    for item in closing_catalog():
        if item.id == item_id:
            return item
    return None


def render_closing_prompt(item: ClosingItem) -> tuple[str, list[Choice]]:
    lines = [
        f"Перед отправкой ТЗ — {item.title_ru}",
        "",
        item.question,
        "",
        f"Зачем это важно: {item.why}",
        "",
        "Варианты:",
    ]
    for i, opt in enumerate(item.options, start=1):
        lines.append(f"{i}. {opt.label}")
    lines.extend(
        [
            "",
            "Можно ответить номером, своими словами или прикрепить файл. "
            "«Готово» отправит черновик как есть.",
        ]
    )
    return "\n".join(lines), list(item.options)


def looks_like_file_answer(text: str) -> bool:
    raw = (text or "").lstrip()
    return raw.startswith("[Файл:") or raw.startswith("[Файл прикреплён:")
