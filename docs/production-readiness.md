# Production Readiness Review

This project is moving from a CLI-first prototype toward a deployable web service. The first six production-readiness tasks completed in this pass are:

1. Deployment packaging with API/web Dockerfiles and local Compose orchestration.
2. CI coverage for Python tests and Next.js production builds.
3. Frontend production build dependency fixes and npm lockfile support.
4. Asynchronous API execution so generation requests return a run identifier immediately.
5. Persisted run progress tracking for polling clients.
6. API-key based access control and database migration scaffolding.

## Operator notes

- Set `BUSINESS_PLAN_API_KEY` in production to require `X-API-Key` on generation, run, and artifact endpoints.
- Run migrations with `alembic upgrade head` before starting the API in production.
- Use object storage and a managed worker queue before high-volume usage; the current background task runner is an incremental step, not the final distributed execution architecture.
