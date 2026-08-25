from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.stt.base import get_stt_provider
from integrations.stt.groq import GroqSTT
from integrations.stt.stub import StubSTT


@pytest.mark.asyncio
async def test_stub_stt_transcribe():
    stt = StubSTT()
    text = await stt.transcribe(b"abc", filename="a.ogg")
    assert "a.ogg" in text
    assert "3 bytes" in text


def test_api_transcribe_does_not_need_project(client):
    res = client.post(
        "/stt/transcribe",
        files={"file": ("note.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    body = res.json()
    assert "stub transcript" in body["text"]
    assert body["stt_provider"] == "StubSTT"


def test_get_stt_provider_groq(monkeypatch):
    from core.config import get_settings

    monkeypatch.setenv("STT_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("STT_MODEL", "whisper-1")
    get_settings.cache_clear()
    try:
        stt = get_stt_provider()
        assert isinstance(stt, GroqSTT)
        assert stt.model == "whisper-large-v3-turbo"
        assert stt.api_key == "gsk_test"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_groq_stt_calls_api():
    stt = GroqSTT(api_key="gsk_test", model="whisper-large-v3-turbo")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "привет мир"}
    mock_response.text = ""

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post.return_value = mock_response

    with patch("integrations.stt.groq.httpx.AsyncClient", return_value=mock_client):
        text = await stt.transcribe(b"audio-bytes", filename="voice.webm")

    assert text == "привет мир"
    mock_client.post.assert_awaited_once()
    args, kwargs = mock_client.post.await_args
    assert "api.groq.com" in args[0]
    assert kwargs["data"]["language"] == "ru"
