from __future__ import annotations

from dataclasses import dataclass, field

from discovery.customer_copy import READY_TOO_EARLY_RU, REVIEW_COVERED_RU
from discovery.fsm import DiscoveryStage
from discovery.literacy import ITLiteracy
from discovery.rephrase import apply_choice_overrides, format_outline_announcement
from discovery.tz_outline import (
    Choice,
    READY_CHOICE,
    OutlinePlan,
    TzTopic,
    question_text,
    remaining_topics,
    resolve_active_topics,
    topic_by_id,
    with_discuss,
)

WELCOME_CREATE_RU = (
    "Добро пожаловать в сессию сбора требований для проекта «{name}».\n\n"
    "Я как консультант: сначала пойму вашу задачу своими словами, потом "
    "задам по одному уточнению — ровно то, без чего нельзя собрать "
    "первую версию (сайт, бот, Mini App, ИИ-агент, автоматизация, "
    "учёт или интеграция).\n\n"
    "Не буду зачитывать анкету и названия разделов. Если чего-то не "
    "хватит именно для вашей задачи — спрошу. Лишнее пропускаю. "
    "Спрошу и то, что меняет срок и стоимость: продвижение (SEO, реклама) "
    "и законы РФ (например 152-ФЗ по персональным данным).\n\n"
    "В конце соберём черновик ТЗ для разработчика. Пока вы не напишете "
    "«пауза» или не попросите передать оставшееся разработчику, "
    "продолжим разговор.\n\n"
    "Если не знаете точный ответ — выберите подсказку или «Обсудить с "
    "разработчиком, что нужно зафиксировать».\n\n"
    "Можно отвечать текстом, голосом, кнопкой-вариантом или прикрепить файл."
)


@dataclass
class DiscoveryPrompt:
    text: str
    choices: list[Choice] = field(default_factory=list)
    topic_id: str | None = None
    stage: DiscoveryStage = DiscoveryStage.UNDERSTANDING_IDEA
    progress: tuple[int, int] = (1, 1)
    multi: bool = False


def welcome_for_create(project_name: str) -> str:
    return WELCOME_CREATE_RU.format(name=project_name or "проект")


def first_topic(
    product_type: str | None = None,
    task_shape: str | None = None,
    plan: OutlinePlan | None = None,
) -> TzTopic:
    topics = resolve_active_topics(product_type, task_shape=task_shape, plan=plan)
    return topics[0]


def build_prompt(
    *,
    stage: DiscoveryStage,
    literacy: ITLiteracy,
    product_type: str | None = None,
    task_shape: str | None = None,
    topic_id: str | None = None,
    done_ids: set[str] | None = None,
    plan: OutlinePlan | None = None,
    captured_snapshots: list[str] | None = None,
    announce_outline: bool = False,
) -> DiscoveryPrompt:
    done = done_ids or set()
    all_topics = resolve_active_topics(product_type, task_shape=task_shape, plan=plan)
    total = max(len(all_topics), 1)
    extras = plan.extra_topics if plan else ()

    if stage == DiscoveryStage.REVIEW:
        leftover = remaining_topics(
            product_type, task_shape=task_shape, done_ids=done, plan=plan
        )
        lines = [
            REVIEW_COVERED_RU if not leftover else READY_TOO_EARLY_RU,
            "",
            "Напишите «готово», чтобы отправить черновик ТЗ владельцу на ревью.",
            "После отправки можно скачать тот же черновик (Markdown, Word, PDF).",
            "«пауза» — остановить интервью и вернуться позже.",
            "Можно дописать уточнение своим текстом.",
        ]
        if leftover:
            lines.insert(
                1,
                "Чтобы закрыть черновик сейчас, напишите «остальное с разработчиком» "
                "— открытые вопросы уйдут владельцу.",
            )
        review_choices = [
            READY_CHOICE,
            Choice("escalate_remaining", "Остальное обсудить с разработчиком", exclusive=True),
            Choice("pause", "Пауза — продолжим позже", exclusive=True),
        ]
        return DiscoveryPrompt(
            text="\n".join(lines),
            choices=review_choices,
            topic_id=None,
            stage=stage,
            progress=(len(done), total),
        )

    topic = topic_by_id(topic_id, extras)
    if topic is None or topic.id in done:
        leftover = remaining_topics(
            product_type, task_shape=task_shape, done_ids=done, plan=plan
        )
        topic = leftover[0] if leftover else None
    if topic is None:
        return build_prompt(
            stage=DiscoveryStage.REVIEW,
            literacy=literacy,
            product_type=product_type,
            task_shape=task_shape,
            done_ids=done,
            plan=plan,
        )

    choices = with_discuss(apply_choice_overrides(topic, plan))
    index = next((i for i, t in enumerate(all_topics) if t.id == topic.id), 0)
    override = (plan.question_overrides.get(topic.id) if plan else None)
    question = question_text(topic, literacy, product_type, override=override)
    lines: list[str] = []
    if announce_outline and plan:
        note = format_outline_announcement(plan)
        if note:
            lines.extend([note, ""])
    _ = captured_snapshots
    lines.append(question)
    return DiscoveryPrompt(
        text="\n".join(lines),
        choices=choices,
        topic_id=topic.id,
        stage=topic.stage,
        progress=(index + 1, total),
        multi=topic.multi,
    )


def question_for(
    stage: DiscoveryStage,
    literacy: ITLiteracy,
    product_type: str | None = None,
    *,
    topic_id: str | None = None,
    task_shape: str | None = None,
    done_ids: set[str] | None = None,
    plan: OutlinePlan | None = None,
) -> str:
    if stage in (DiscoveryStage.PROJECT_CREATED, DiscoveryStage.READY_FOR_OWNER):
        return ""
    return build_prompt(
        stage=stage,
        literacy=literacy,
        product_type=product_type,
        task_shape=task_shape,
        topic_id=topic_id,
        done_ids=done_ids,
        plan=plan,
    ).text
