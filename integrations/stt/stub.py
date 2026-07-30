from integrations.stt.base import SpeechToText


class StubSTT(SpeechToText):
    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        size = len(audio or b"")
        return f"[stub transcript for {filename}; {size} bytes]"
