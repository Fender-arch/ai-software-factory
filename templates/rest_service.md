# Product type: rest_service

## Typical MVP

- Small HTTP API
- One primary resource CRUD
- Auth simple (API key or basic JWT)
- OpenAPI docs

## Discovery checklist

- [ ] Resources and operations
- [ ] Auth model
- [ ] Consumers (who calls the API)
- [ ] SLA / volume expectations (keep modest)
- [ ] Deployment target

## Out of scope for this template

Event-driven microservices mesh, multi-region, complex CQRS.
