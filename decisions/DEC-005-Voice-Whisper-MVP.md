# DEC-005 — Voice / Whisper in MVP

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |

## Context

Customers often prefer speaking requirements in Telegram. The design discussion included voice→text as part of MVP.

## Decision

MVP includes voice → text via Whisper-compatible STT. Transcripts enter the same Discovery pipeline as text.

Providers: `STT_PROVIDER=stub` (dev), `groq` (recommended cheap cloud Whisper), `whisper` (OpenAI). Mini App prefers **Web Speech API** when the client environment supports it; otherwise records audio and calls server STT (Groq/OpenAI).

## Consequences

- `integrations/stt` is a first-class module
- Voice is not deferred to Future
- Cost/latency of STT must be monitored; failures should ask the user to resend text
- Set `GROQ_API_KEY` when using `STT_PROVIDER=groq`
