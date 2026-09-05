"""Customer-facing Discovery copy. Catalog titles stay out of the chat.

The TZ outline is an internal coverage checklist (DEC-008, DEC-014).
Replies, welcome text, and Mini App progress must not read out section
names as a questionnaire menu.
"""

from __future__ import annotations

import re

COVERAGE_CONTINUE_RU = (
    "Давай уточним ещё пару вещей для сборки — без этого черновик будет дырявым."
)

READY_TOO_EARLY_RU = (
    "Ещё рано закрывать черновик: для сборки не хватает пары уточнений. "
    "Продолжим текущий вопрос, напишите «пауза» или "
    "«остальное с разработчиком»."
)

REVIEW_COVERED_RU = (
    "Кажется, для сборки уже достаточно. Проверьте уточнения "
    "и подтвердите отправку черновика владельцу."
)

PAUSE_RU = (
    "Интервью на паузе — черновик ТЗ пока не отправляю владельцу.\n\n"
    "Напишите «продолжить», когда будете готовы."
)

# Lines / sentences that turn the reply into a TZ section menu.
_CATALOG_MENU_LINE_RE = re.compile(
    r"(?im)^(?:.*"
    r"(?:раздел(?:ы)?\s+тз|подраздел\s+тз"
    r"|осталось пройти разделы"
    r"|не покрыты разделы"
    r"|ещё не закрыто:"
    r"|закрыто:"
    r"|добавляю:"
    r"|не спрашиваю\s*\("
    r"|сейчас открыт раздел:"
    r"|собрал перечень разделов"
    r")).*$"
)
_SECTION_N_RE = re.compile(r"раздел(?:ы)?\s+\d+", re.I)
_RAZDEL_COLON_RE = re.compile(r"раздел:", re.I)


def looks_like_catalog_menu(text: str) -> bool:
    """True when customer copy lists catalog sections as a form."""
    blob = text or ""
    if _CATALOG_MENU_LINE_RE.search(blob):
        return True
    if _SECTION_N_RE.search(blob):
        return True
    if _RAZDEL_COLON_RE.search(blob):
        return True
    return False


def strip_catalog_menu(text: str) -> str:
    """Drop questionnaire lines; keep the conversational remainder."""
    if not (text or "").strip():
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if _CATALOG_MENU_LINE_RE.search(line):
            continue
        if _SECTION_N_RE.search(line) or _RAZDEL_COLON_RE.search(line):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def coverage_continue_reply(existing: str) -> str:
    """Soft coverage-gate follow-up: no leftover title_ru list."""
    cleaned = sanitize_customer_reply(existing)
    if COVERAGE_CONTINUE_RU in cleaned:
        return cleaned
    if cleaned:
        return f"{cleaned}\n\n{COVERAGE_CONTINUE_RU}"
    return COVERAGE_CONTINUE_RU


def reply_lists_topic_titles(reply: str, titles: list[str]) -> bool:
    """True when two or more catalog titles appear in the customer reply."""
    blob = reply or ""
    hits = [title for title in titles if title and title in blob]
    return len(hits) >= 2


# Recap clauses of already-accepted answers (keep the question after them).
_ECHO_CLAUSE_RE = re.compile(
    r"(?i)вы\s+описали\s*:\s*«[^»]+»\s*[.!]?\s*"
    r"|как\s+вы\s+(?:сказали|описали)[^.?!\n]*[.?]?\s*"
    r"|уже\s+зафиксировали\s*:[^.?!\n]*[.?]?\s*"
    r"|понял(?:а|и)?\s+задачу\s+про\s*«[^»]+»\s*[.!]?\s*"
    r"|по\s+задаче\s*«[^»]+»\s*[—–-]?\s*"
)
_QUOTED_FOR_RE = re.compile(r"(?i)для\s*«[^»]{10,}»\s*:?\s*")


def strip_prior_answer_echo(text: str) -> str:
    """Drop recap of already captured answers; keep the actual question."""
    if not (text or "").strip():
        return ""
    cleaned = _ECHO_CLAUSE_RE.sub("", text)
    cleaned = _QUOTED_FOR_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"^[.?!,\s]+", "", cleaned)
    return cleaned.strip()


def sanitize_customer_reply(text: str) -> str:
    """Catalog menu + prior-answer echo stay out of the customer chat."""
    return strip_prior_answer_echo(strip_catalog_menu(text))
