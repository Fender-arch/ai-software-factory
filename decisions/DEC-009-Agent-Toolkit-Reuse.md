# DEC-009 — Agent toolkit reuse (patterns, not wholesale vendors)

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-09-05 |

## Context

The factory already has `AGENTS.md`, `.cursor/rules`, `.cursor/skills/asf-mvp`, `docs/12-Agent-Toolkit.md`, `prompts/`, and `templates/`. Open Cursor/Claude packs (progressive disclosure, interview-me, DESIGN.md, continual-learning, OWASP skills, Spec Kit, Rive notes) are useful **as patterns**. Vendoring those repos, always-on mega-rules, or a multi-agent runtime would fight DEC-002 and the token budget.

Two audiences must share conventions without sharing the factory internals: (A) people developing ASF, (B) customer MVP repos the factory stamps.

## Decision

**Adopt patterns, write our own thin files:**

| Pattern | What we keep |
|---------|----------------|
| Progressive disclosure (DVC2 / Shiplight-style) | `AGENTS.md` is a router; `alwaysApply` stays `asf.mdc` only; details in skills with good `description`; globs on `.mdc` |
| interview-me / spec-builder tone | Stronger `prompts/discovery-interview.md` + skill `human-interview` |
| DESIGN.md + design rule | `templates/DESIGN.md`, `anti-slop-design`, `design-anti-slop.mdc` |
| Continual-learning *ideas* | Learned sections in `AGENTS.md` + skill `project-memory`. Document enabling Cursor’s plugin; **do not** copy proprietary hook TypeScript |
| security-review / OWASP Top 10 shape | Read-mostly skill + `security-basics.mdc` (Telegram token, Mini App initData) |
| autodoc | Skill + existing `docs-ru-sync` hook |
| Spec Kit | Export mapping skill + `templates/speckit/*` stubs; **do not** vendor spec-kit |
| Rive / Experience Layer | Mini App mascot slice is [DEC-011](DEC-011-Experience-Layer-Mascot.md); do not vendor external Rive kits |
| Customer pack | `mvp-customer-pack` stamps a slim `templates/customer-agents/AGENTS.md` |

Product type `mobile_native` is in scope (see [DEC-010](DEC-010-Mobile-Native.md)).

**Rejected:**

| Temptation | Why |
|------------|-----|
| Multi-agent swarm / extra OS agent processes | [DEC-002](DEC-002-AI-Coordinator.md) |
| OpenReq or other requirements-runtime engines | Discovery + KG already own the interview contract |
| Always-on mega rules / dumped catalogs | Token cost; hides the router |
| Wholesale vendor of external skill repos | License and drift; we need ASF-shaped files |
| Proprietary continual-learning hook TS | License unclear; our skill is enough |
| Redis / Neo4j / event bus as “memory” | [DEC-001](DEC-001-Knowledge-Graph.md), [DEC-004](DEC-004-No-Redis-in-MVP.md) |

## Consequences

- Agents load one skill per task. New toolkit files must pass the token-economy test (`token-economy` skill).
- Customer exports get a pack, not a copy of ASF epics.
- Docs live in `docs/12-Agent-Toolkit.md` (EN canon + RU mirror).
