from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Settings


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        raise NotImplementedError


def get_stt_provider(settings: Settings | None = None) -> SpeechToText:
    from core.config import get_settings
    from integrations.stt.stub import StubSTT
    from integrations.stt.whisper import WhisperSTT

    settings = settings or get_settings()
    if settings.stt_provider == "whisper":
        return WhisperSTT(api_key=settings.openai_api_key, model=settings.stt_model)
    return StubSTT()
