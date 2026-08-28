from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Isolate tests from developer .env (whisper STT, owner id, etc.).
os.environ["STT_PROVIDER"] = "stub"
os.environ["LLM_PROVIDER"] = "stub"
os.environ["OWNER_TELEGRAM_ID"] = ""
os.environ["CONSOLE_TOKEN"] = ""
os.environ["ASF_ENV"] = "local"
os.environ["ASF_DEBUG"] = "true"
os.environ["ASF_ESTIMATE_HOURLY_RATE"] = "3000"
os.environ["ASF_ESTIMATE_CURRENCY"] = "RUB"

from apps.api.main import app
from core.config import get_settings
from core.db import Base, get_db
import core.models  # noqa: F401

get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
