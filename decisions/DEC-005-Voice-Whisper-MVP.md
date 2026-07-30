# DEC-005 — Voice / Whisper in MVP

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-07-30 |

## Context

Customers often prefer speaking requirements in Telegram. The design discussion included voice→text as part of MVP.

## Decision

MVP includes Telegram voice messages transcribed via Whisper (or compatible STT). Transcripts enter the same Discovery pipeline as text. Local/dev may use `STT_PROVIDER=stub`.

## Consequences

- `integrations/stt` is a first-class module
- Voice is not deferred to Future
- Cost/latency of STT must be monitored; failures should ask the user to resend text
