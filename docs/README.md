# ASF Foundation docs

| Field | Value |
|-------|-------|
| Status | Accepted |
| Version | 0.1 |
| Updated | 2026-07-31 |
| Owner | ASF Core |

## Source of truth

English files in this folder (`docs/*.md`, including `15-Owner-TZ-Console.md` and `16-VPS-Deploy.md`) are **canonical** for agents, ADRs, and implementation.

Russian mirror copies live in [`docs/ru/`](ru/) for human reading. They must not override English decisions.

When an English doc changes, update the matching file under `docs/ru/` (Cursor hooks + rules enforce this in agent sessions).

## Index

| Doc | Topic |
|-----|-------|
| [00-Vision.md](00-Vision.md) | Product vision |
| [01-MVP-Scope.md](01-MVP-Scope.md) | MVP in / out of scope |
| [02-Architecture.md](02-Architecture.md) | Modular monolith |
| [03-Tech-Stack.md](03-Tech-Stack.md) | Locked stack |
| [04-Repository-Structure.md](04-Repository-Structure.md) | Layout |
| [05-Roadmap.md](05-Roadmap.md) | Delivery weeks |
| [06-Coding-Standards.md](06-Coding-Standards.md) | Code style |
| [07-AI-Rules.md](07-AI-Rules.md) | Coordinator + Cursor rules |
| [08-Discovery.md](08-Discovery.md) | Discovery FSM |
| [09-Knowledge-Graph.md](09-Knowledge-Graph.md) | Entity / relation model |
| [10-Project-Principles.md](10-Project-Principles.md) | Design principles |
| [11-Glossary.md](11-Glossary.md) | Terms |
| [12-Agent-Toolkit.md](12-Agent-Toolkit.md) | Rules / skills map |
| [13-Dev-Setup.md](13-Dev-Setup.md) | Local runbook |
| [14-Telegram-Customer-UX.md](14-Telegram-Customer-UX.md) | Mini App customer UX |
| [15-Owner-TZ-Console.md](15-Owner-TZ-Console.md) | Owner TZ graph console |
| [16-VPS-Deploy.md](16-VPS-Deploy.md) | VPS deploy next to an existing website |
