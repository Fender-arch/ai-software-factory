---
name: security-review
description: >-
  Read-mostly OWASP-oriented security review for ASF and customer MVPs:
  injection, authz, secrets, SSRF, Telegram bot tokens, Mini App initData.
  Use before merge, when touching apps/api, integrations, auth, uploads, or
  generated customer backends. Do not write exploit PoCs.
---

# Security review (read-mostly)

Checklist, not an attack guide. Report findings with file paths and a fix direction. Do not write exploits, payloads, or reproduction procedures.

Companion rule (globs): `.cursor/rules/security-basics.mdc`.

## Scope

| Surface | Look at |
|---------|---------|
| ASF API | `apps/api`, `core`, uploads, console API |
| Integrations | Telegram bot token, webhook secrecy, STT keys |
| Mini App | `initData` validation, `?uid=` smoke-only bypass |
| Customer MVP | Same classes of bug in the generated repo |

## OWASP-oriented pass (MVP)

1. **Injection** — SQL via SQLAlchemy parameters only; no f-string SQL; no unsanitized HTML in Mini App/console.
2. **Broken authz** — owner HITL vs customer project isolation; console is not a public portal; do not trust client-supplied `project_id` without membership.
3. **Secrets** — bot token, `OPENAI_API_KEY` / Groq, `OWNER_TELEGRAM_ID` never in logs, Learned sections, artifacts, or client JS.
4. **SSRF** — user-supplied URLs (design references, webhooks, file fetches) must not be fetched unsafely by the server.
5. **XSS** — Mini App and console: text into DOM must be escaped; no `innerHTML` of customer TZ text.
6. **CSRF / session** — cookie or header rules for `/console/api` and customer APIs; Telegram initData is not a browser cookie.
7. **Upload / path** — `UPLOAD_DIR` paths stay under the upload root; no user-controlled path segments.
8. **Dependency / default creds** — no committed `.env`; Docker ports as in deploy docs.

## Telegram & Mini App

- Bot token only in server env; never shipped to Mini App JS.
- Validate Telegram **initData** HMAC on the API for privileged actions. `?uid=` is local smoke, not production auth.
- Treat inbound message text as untrusted (length caps already exist — keep them).
- Do not log raw `initData`, phone numbers, or voice bytes.

## Output

A short list: severity, location, what is wrong, how to harden. If the change is a fix in a tree the user maintains, implement the fix. If asked for both a fix and an exploit/PoC: **fix only**.
