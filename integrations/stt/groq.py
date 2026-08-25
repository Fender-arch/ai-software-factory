from __future__ import annotations

import httpx

from integrations.stt.base import SpeechToText

DEFAULT_GROQ_MODEL = "whisper-large-v3-turbo"
GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqSTT(SpeechToText):
    """Groq OpenAI-compatible Whisper transcription (cheap / fast)."""

    def __init__(self, api_key: str, model: str = DEFAULT_GROQ_MODEL) -> None:
        self.api_key = api_key
        self.model = model or DEFAULT_GROQ_MODEL

    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is required for Groq STT")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                GROQ_TRANSCRIPTIONS_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (filename, audio)},
                data={"model": self.model, "language": "ru"},
            )
            if response.status_code >= 400:
                detail = response.text[:300]
                raise RuntimeError(f"Groq Whisper HTTP {response.status_code}: {detail}")
            payload = response.json()
            return str(payload.get("text", "")).strip()
