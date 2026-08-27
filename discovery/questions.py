from __future__ import annotations

from dataclasses import dataclass, field

from discovery.fsm import DiscoveryStage
from discovery.literacy import ITLiteracy
from discovery.rephrase import apply_choice_overrides, format_outline_announcement, topic_title
from discovery.tz_outline import (
    Choice,
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
    "Это интервью: сначала пойму задачу. Затем соберу перечень разделов ТЗ "
    "именно под неё — столько, сколько нужно, чтобы по ответам "
    "можно было реализовать первую версию (сайт, бот, Mini App, "
    "ИИ-агент, автоматизация, учёт или интеграция). Спрошу и то, "
    "что меняет срок и стоимость: продвижение (SEO, реклама) и "
    "законы РФ (например 152-ФЗ по персональным данным).\n\n"
    "Каждый раз — один раздел. Если чего-то не хватит для этой задачи, "
    "добавлю подраздел. Лишнее спрашивать не буду. Вопросы и варианты "
    "ответов перепишу под вашу формулировку задачи.\n\n"
    "Покрываем применимые разделы, пока вы не напишете «пауза» или не "
    "попросите передать оставшееся разработчику.\n\n"
    "Если не знаете точный ответ — выберите вариант или «Обсудить с "
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
        covered = [topic_title(t, plan) for t in all_topics if t.id in done]
        lines = [
            f"Разделы ТЗ пройдены: {len(done)}/{total}.",
            "",
        ]
        if covered:
            lines.append("Закрыто: " + "; ".join(covered[-8:]))
            lines.append("")
        if leftover:
            lines.append(
                "Ещё не закрыто: " + "; ".join(topic_title(t, plan) for t in leftover) + "."
            )
            lines.append(
                "Чтобы закрыть черновик сейчас, напишите «остальное с разработчиком» "
                "— открытые разделы уйдут владельцу как вопросы."
            )
        else:
            lines.append("Критических пробелов по разделам нет.")
        lines.extend(
            [
                "",
                "Напишите «готово», чтобы отправить черновик ТЗ владельцу на ревью.",
                "После отправки можно скачать тот же черновик (Markdown, Word, PDF).",
                "«пауза» — остановить интервью и вернуться позже.",
                "Можно дописать уточнение своим текстом.",
            ]
        )
        review_choices = [
            Choice("ready", "Готово — отправить черновик ТЗ владельцу", exclusive=True),
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
    header = f"Раздел ТЗ {index + 1}/{total} — {topic_title(topic, plan)}"
    if topic.parent_id or topic.dynamic:
        header = f"Подраздел ТЗ {index + 1}/{total} — {topic_title(topic, plan)}"
    override = (plan.question_overrides.get(topic.id) if plan else None)
    question = question_text(topic, literacy, product_type, override=override)
    lines: list[str] = []
    if announce_outline and plan:
        lines.extend([format_outline_announcement(plan), ""])
    _ = captured_snapshots
    lines.extend([header, "", question])
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
