# Product type: rest_service

## Typical MVP

- Small HTTP API
- One primary resource CRUD
- Auth simple (API key or basic JWT)
- OpenAPI docs

## Discovery checklist

- [ ] Resources and operations (or tables + admin actions)
- [ ] Auth model
- [ ] Consumers (who calls the API / who edits data)
- [ ] Data fields and volume (keep modest)
- [ ] Integration mapping if this is a system-to-system job
- [ ] SLA / volume expectations (keep modest)
- [ ] Deployment target
- [ ] Legal: 152-FZ / personal data if the API stores citizen data (impacts estimate)
- [ ] Timeline and budget
- [ ] Contact details and preferred channel
- [ ] Acceptance

## Out of scope for this template

Event-driven microservices mesh, multi-region, complex CQRS.
