from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.db import Base
from core.models import Project, ProjectStatus
import core.models  # noqa: F401
from core.tz_document import (
    CLIENT_TZ_TITLE,
    compose_tz_markdown,
    export_markdown_file,
    heading_anchor,
    resolve_owner_contacts,
)
from knowledge.repository import KnowledgeRepository

_FORBIDDEN_CLIENT = (
    "Appendix",
    "Draft TZ",
    "draft TZ",
    "черновик Draft",
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _project(db, *, name="Пекарня у дома", payload: dict | None = None) -> Project:
    project = Project(
        name=name,
        status=ProjectStatus.WAITING_OWNER,
        product_type="website",
        customer_telegram_id="55001",
    )
    db.add(project)
    db.flush()
    kg = KnowledgeRepository(db)
    kg.create_entity(
        project.id,
        "Project",
        name,
        payload={
            "status": project.status.value,
            "product_type": "website",
            "task_shape": "shape_website",
            **(payload or {}),
        },
    )
    return project


def _req(kg, project, topic_id: str, description: str, *, name: str | None = None) -> None:
    kg.create_entity(
        project.id,
        "Requirement",
        name or description[:40],
        status="processed",
        payload={
            "topic_id": topic_id,
            "description": description,
            "priority": "must",
        },
    )


def _seed_full(db, *, project_payload: dict | None = None) -> Project:
    project = _project(db, payload=project_payload)
    kg = KnowledgeRepository(db)
    _req(kg, project, "purpose_problem", "Нужен сайт витрины пекарни с заявками.")
    _req(kg, project, "contacts", "Иван Петров, +7 900 111-22-33, baker@example.com")
    _req(kg, project, "preferred_contact", "Telegram в рабочие часы")
    _req(kg, project, "must_features", "Каталог изделий с фото")
    _req(kg, project, "must_features", "Форма заявки на торт")
    _req(kg, project, "closing_additions", "Нужна тёмная тема на главной")
    _req(
        kg,
        project,
        "owner_review_supplement",
        "Кнопка «Позвонить» после ревью владельца",
    )
    kg.create_entity(
        project.id,
        "OpenQuestion",
        "hosting",
        status="open",
        payload={"question": "Кто оплачивает хостинг в первый год?"},
    )
    kg.create_entity(
        project.id,
        "Risk",
        "photos",
        payload={"description": "Нет готовых фото витрины к запуску"},
    )
    db.flush()
    return project


def test_heading_anchor_is_stable_for_numbered_ru_titles():
    assert heading_anchor("1. Цель и проблема") == "1-цель-и-проблема"
    assert heading_anchor("12. Открытые вопросы") == "12-открытые-вопросы"


def test_compose_tz_markdown_client_structure(db, monkeypatch):
    monkeypatch.setenv("STUDIO_NAME", "Студия Север")
    monkeypatch.setenv("OWNER_CONTACT_NAME", "Дмитрий")
    monkeypatch.setenv("OWNER_CONTACT_EMAIL", "studio@example.com")
    monkeypatch.setenv("OWNER_CONTACT_PHONE", "+7 111 000-00-00")
    monkeypatch.setenv("OWNER_CONTACT_TELEGRAM", "@studio_north")
    get_settings.cache_clear()
    try:
        project = _seed_full(db)
        md = compose_tz_markdown(db, project)
    finally:
        get_settings.cache_clear()

    assert md.startswith(f"# {CLIENT_TZ_TITLE} — Пекарня у дома")
    assert "черновик" not in md.lower()
    for phrase in _FORBIDDEN_CLIENT:
        assert phrase not in md

    assert "## Мета" in md
    assert "**Проект:** Пекарня у дома" in md
    assert "### Контакты заказчика" in md
    assert "Telegram заказчика: `55001`" in md
    assert "Иван Петров" in md
    assert "Предпочтительный канал: Telegram в рабочие часы" in md
    assert "### Контакты исполнителя" in md
    assert "Студия: Студия Север" in md
    assert "Имя: Дмитрий" in md
    assert "Email: studio@example.com" in md

    toc_at = md.index("## Оглавление")
    first_section_at = md.index("## 1. ")
    assert toc_at < first_section_at
    assert "## 1. Цель и проблема" in md
    assert f"[Цель и проблема](#{heading_anchor('1. Цель и проблема')})" in md
    assert "**ТЗ-1.1**" in md
    assert "Нужен сайт витрины пекарни" in md

    must = re.search(r"## (\d+)\. Обязательные функции", md)
    assert must, md
    n = must.group(1)
    assert f"**ТЗ-{n}.1**" in md
    assert f"**ТЗ-{n}.2**" in md
    assert "Каталог изделий с фото" in md
    assert "Форма заявки на торт" in md

    assert "Нужна тёмная тема на главной" in md
    assert "Кнопка «Позвонить» после ревью владельца" in md
    assert "Кто оплачивает хостинг" in md
    assert re.search(r"\*\*ТЗ-\d+\.1\*\* Кто оплачивает хостинг", md)
    assert "Нет готовых фото витрины" in md

    numbered = re.findall(r"^## (\d+)\. ", md, flags=re.M)
    assert numbered == [str(i) for i in range(1, len(numbered) + 1)]
    toc_links = re.findall(r"^\d+\. \[.+\]\(#.+\)$", md, flags=re.M)
    assert len(toc_links) == len(numbered)


def test_owner_contacts_payload_overrides_env(db, monkeypatch):
    monkeypatch.setenv("STUDIO_NAME", "Env Studio")
    monkeypatch.setenv("OWNER_CONTACT_NAME", "Env Name")
    get_settings.cache_clear()
    try:
        project = _seed_full(
            db,
            project_payload={
                "owner_contacts": {
                    "studio": "Пекарня Продакшн",
                    "name": "Мария",
                    "telegram": "@baker_dev",
                }
            },
        )
        md = compose_tz_markdown(db, project)
        resolved = resolve_owner_contacts(
            {"owner_contacts": {"studio": "Пекарня Продакшн", "name": "Мария"}}
        )
    finally:
        get_settings.cache_clear()

    assert resolved["studio"] == "Пекарня Продакшн"
    assert "Пекарня Продакшн" in md
    assert "Имя: Мария" in md
    assert "Env Studio" not in md
    assert "Env Name" not in md


def test_owner_contacts_empty_when_unset(monkeypatch):
    monkeypatch.delenv("STUDIO_NAME", raising=False)
    monkeypatch.delenv("OWNER_CONTACT_NAME", raising=False)
    monkeypatch.delenv("OWNER_CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("OWNER_CONTACT_PHONE", raising=False)
    monkeypatch.delenv("OWNER_CONTACT_TELEGRAM", raising=False)
    get_settings.cache_clear()
    try:
        contacts = resolve_owner_contacts({})
    finally:
        get_settings.cache_clear()
    assert contacts == {
        "studio": "",
        "name": "",
        "email": "",
        "phone": "",
        "telegram": "",
        "note": "",
    }


def test_client_export_pipeline_strips_draft_markers(db):
    project = _seed_full(db)
    md = compose_tz_markdown(db, project)
    payload, media, filename = export_markdown_file(md, project.name, "md")
    text = payload.decode("utf-8")
    assert media.startswith("text/markdown")
    assert filename.endswith(".md")
    assert CLIENT_TZ_TITLE in text
    for phrase in _FORBIDDEN_CLIENT:
        assert phrase not in text

    docx, docx_media, docx_name = export_markdown_file(md, project.name, "docx")
    assert docx[:2] == b"PK"
    assert "wordprocessingml" in docx_media
    assert docx_name.endswith(".docx")

    pdf, pdf_media, pdf_name = export_markdown_file(md, project.name, "pdf")
    assert pdf.startswith(b"%PDF")
    assert pdf_media == "application/pdf"
    assert pdf_name.endswith(".pdf")
