import pytest

from integrations.stt.stub import StubSTT


@pytest.mark.asyncio
async def test_stub_stt_transcribe():
    stt = StubSTT()
    text = await stt.transcribe(b"abc", filename="a.ogg")
    assert "a.ogg" in text
    assert "3 bytes" in text
