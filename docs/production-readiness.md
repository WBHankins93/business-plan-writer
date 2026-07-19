# Production Readiness Review

This project is moving from a CLI-first prototype toward a deployable web service. The first six production-readiness tasks completed in this pass are:

1. Deployment packaging with API/web Dockerfiles and local Compose orchestration.
2. CI coverage for Python tests and Next.js production builds.
3. Frontend production build dependency fixes and npm lockfile support.
4. Asynchronous API execution so generation requests return a run identifier immediately.
5. Persisted run progress tracking for polling clients.
6. API-key based access control, explicit database migrations, and schema readiness checks.

## Operator notes

- Set `BUSINESS_PLAN_API_KEY` in production to require `X-API-Key` on generation, run, and artifact endpoints.
- Run migrations with `alembic upgrade head` before starting the API in production.
- API startup never applies migrations. `/healthz` reports process liveness; `/readyz` returns
  `503` until the database revision matches the Alembic head.
- Artifacts live under `ARTIFACT_ROOT/{run_id}/`. Polling returns short-lived signed download
  links when API-key protection is enabled; the API key itself is never placed in a URL.
- `PIPELINE_TIMEOUT_SECONDS` bounds each pipeline subprocess (default: 900 seconds).
- Use object storage and a managed worker queue before high-volume usage; the current background task runner is an incremental step, not the final distributed execution architecture.

For Compose, migrate and start as separate operations:

```bash
docker compose --env-file .env.local run --rm migrate
docker compose --env-file .env.local up --build
```
