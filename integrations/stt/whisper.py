from __future__ import annotations

import httpx

from integrations.stt.base import SpeechToText


class WhisperSTT(SpeechToText):
    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        self.api_key = api_key
        self.model = model

    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for Whisper STT")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (filename, audio)},
                data={"model": self.model, "language": "ru"},
            )
            if response.status_code >= 400:
                detail = response.text[:300]
                raise RuntimeError(
                    f"Whisper HTTP {response.status_code}: {detail}"
                )
            payload = response.json()
            return str(payload.get("text", "")).strip()
