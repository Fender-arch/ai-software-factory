"""LLM-driven Discovery turns (DEC-008): scripted fake LLM + guard rails."""

from __future__ import annotations

import json

import pytest

from core.config import get_settings


def _is_interview_prompt(system: str) -> bool:
    return "LLM interviewer" in system


def _fake_interviewer(system, user):
    """Scripted interviewer: captures the first remaining topic each turn."""
    if not _is_interview_prompt(system):
        return {}  # outline adaptation: keep the heuristic plan
    ctx = json.loads(user)
    remaining = [t for t in ctx["topics"] if t["status"] == "remaining"]
    if not remaining:
        return {
            "reply_to_customer": "Все разделы закрыты — отправляю черновик владельцу.",
            "captured": [],
            "chips": [],
            "next_action": "ready_for_owner",
        }
    topic = remaining[0]
    if topic["id"] == "success_mvp":
        summary = "MVP success: 80% of test bookings complete without staff help."
    else:
        summary = (
            f"Customer gave a concrete implementable answer "
            f"for the {topic['id']} section."
        )
    return {
        "reply_to_customer": f"Понял вас. Теперь про раздел «{topic['title_ru']}».",
        "captured": [
            {
                "topic_id": topic["id"],
                "summary_en": summary,
                "sufficient": True,
            }
        ],
        "chips": [
            {"id": "opt_a", "label": "Вариант А"},
            {"id": "opt_b", "label": "Вариант Б", "recommended": True},
        ],
        "next_action": "continue",
    }


@pytest.fixture()
def llm_client(client, monkeypatch):
    monkeypatch.setenv("DISCOVERY_ENGINE", "llm")
    get_settings.cache_clear()
    monkeypatch.setattr("discovery.interview._llm_json", _fake_interviewer)
    yield client
    get_settings.cache_clear()


def _create_project(client) -> str:
    res = client.post(
        "/projects",
        json={"name": "LLM Interview", "customer_telegram_id": "llm-user"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def _send(client, project_id: str, text: str):
    res = client.post(
        f"/projects/{project_id}/messages",
        json={"text": text, "role": "customer"},
    )
    assert res.status_code == 201
    return res


def test_llm_interview_reaches_waiting_owner(llm_client):
    project_id = _create_project(llm_client)
    last = None
    for i in range(60):
        last = _send(
            llm_client,
            project_id,
            f"Хочу сайт для студии, детальный ответ номер {i} на ваш вопрос.",
        )
        body = last.json()
        if body["project_status"] == "WAITING_OWNER":
            break
    else:
        raise AssertionError("LLM discovery did not reach WAITING_OWNER")

    body = last.json()
    assert body["tz_available"] is True
    assert body["discovery_stage"] == "READY_FOR_OWNER"

    tz = llm_client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.status_code == 200
    assert tz.json()["content"]


def test_llm_reply_is_conversational_and_chips_sanitized(llm_client):
    project_id = _create_project(llm_client)
    res = _send(llm_client, project_id, "Хочу сайт для записи клиентов в салон.")
    body = res.json()
    assert body["discovery_reply"].startswith("Понял вас.")

    choices = body["discovery_choices"]
    assert choices, "expected LLM chips plus the discuss chip"
    discuss = [c for c in choices if c["id"] == "discuss_with_developer"]
    assert len(discuss) == 1 and discuss[0]["exclusive"] is True
    assert len(choices) <= 6
    assert all(len(c["label"]) <= 180 for c in choices)
    regular = [c for c in choices if c["id"] != "discuss_with_developer"]
    assert sum(1 for c in regular if c.get("recommended")) <= 1


def test_llm_ready_for_owner_blocked_until_coverage(llm_client, monkeypatch):
    def always_ready(system, user):
        if not _is_interview_prompt(system):
            return {}
        return {
            "reply_to_customer": "Давайте закроем ТЗ прямо сейчас.",
            "captured": [],
            "chips": [],
            "next_action": "ready_for_owner",
        }

    monkeypatch.setattr("discovery.interview._llm_json", always_ready)
    project_id = _create_project(llm_client)
    res = _send(llm_client, project_id, "Просто идея без деталей, давайте финализировать.")
    body = res.json()
    assert body["project_status"] != "WAITING_OWNER"
    assert body["discovery_stage"] != "READY_FOR_OWNER"
    assert "осталось пройти разделы" in body["discovery_reply"]


def test_llm_invalid_output_falls_back_to_fsm(llm_client, monkeypatch):
    monkeypatch.setattr("discovery.interview._llm_json", lambda system, user: None)
    project_id = _create_project(llm_client)
    res = _send(llm_client, project_id, "Хочу сайт для студии UNI4IT.")
    body = res.json()
    assert "Раздел ТЗ" in body["discovery_reply"]


def test_llm_unknown_topic_ids_are_dropped(llm_client, monkeypatch):
    def hallucinating(system, user):
        if not _is_interview_prompt(system):
            return {}
        return {
            "reply_to_customer": "Записал ответ на несуществующий раздел.",
            "captured": [
                {
                    "topic_id": "made_up_topic",
                    "summary_en": "Hallucinated topic capture attempt.",
                    "sufficient": True,
                }
            ],
            "chips": [],
            "next_action": "continue",
        }

    monkeypatch.setattr("discovery.interview._llm_json", hallucinating)
    project_id = _create_project(llm_client)
    res = _send(llm_client, project_id, "Отвечаю на ваш вопрос подробно.")
    assert res.status_code == 201
    body = res.json()
    assert body["discovery_reply"] == "Записал ответ на несуществующий раздел."

    ws = llm_client.get(
        f"/projects/{project_id}/workspace",
        params={"customer_telegram_id": "llm-user", "mode": "create"},
    )
    assert ws.status_code == 200
    progress = ws.json()["discovery_progress"]
    assert progress["done"] == 0


def test_llm_captures_multiple_topics_per_message(llm_client, monkeypatch):
    def greedy(system, user):
        if not _is_interview_prompt(system):
            return {}
        ctx = json.loads(user)
        remaining = [t for t in ctx["topics"] if t["status"] == "remaining"]
        captured = [
            {
                "topic_id": t["id"],
                "summary_en": f"Concrete captured fact for {t['id']} section.",
                "sufficient": True,
            }
            for t in remaining[:2]
        ]
        return {
            "reply_to_customer": "Принято, зафиксировал сразу два раздела.",
            "captured": captured,
            "chips": [],
            "next_action": "continue",
        }

    monkeypatch.setattr("discovery.interview._llm_json", greedy)
    project_id = _create_project(llm_client)
    _send(llm_client, project_id, "Рассказываю сразу про цель и тип решения: сайт.")
    ws = llm_client.get(
        f"/projects/{project_id}/workspace",
        params={"customer_telegram_id": "llm-user", "mode": "create"},
    )
    assert ws.status_code == 200
    assert ws.json()["discovery_progress"]["done"] >= 2


def test_draft_tz_polished_by_llm(llm_client, monkeypatch):
    def polishing(system, user):
        if "TZ polish" in system:
            ctx = json.loads(user)
            return {
                "polished_markdown": ctx["draft_markdown"] + "\n\n> Отполировано LLM.\n"
            }
        return _fake_interviewer(system, user)

    monkeypatch.setattr("discovery.interview._llm_json", polishing)
    project_id = _create_project(llm_client)
    last = None
    for i in range(60):
        last = _send(
            llm_client,
            project_id,
            f"Хочу сайт для студии, детальный ответ номер {i} на ваш вопрос.",
        )
        if last.json()["project_status"] == "WAITING_OWNER":
            break
    else:
        raise AssertionError("LLM discovery did not reach WAITING_OWNER")

    tz = llm_client.get(f"/projects/{project_id}/artifacts/draft-tz")
    assert tz.status_code == 200
    assert "Отполировано LLM" in tz.json()["content"]


def test_pause_intent_stays_deterministic(llm_client, monkeypatch):
    calls: list[str] = []

    def counting(system, user):
        if _is_interview_prompt(system):
            calls.append("interview")
            return _fake_interviewer(system, user)
        return {}

    monkeypatch.setattr("discovery.interview._llm_json", counting)
    project_id = _create_project(llm_client)
    res = _send(llm_client, project_id, "пауза")
    body = res.json()
    assert body["paused"] is True
    assert calls == [], "pause intent must not reach the LLM"
