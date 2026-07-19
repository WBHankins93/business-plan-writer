# Production Readiness Review

This project is moving from a CLI-first prototype toward a deployable web service. The first six production-readiness tasks completed in this pass are:

1. Deployment packaging with API/web Dockerfiles and local Compose orchestration.
2. CI coverage for Python tests and Next.js production builds.
3. Frontend production build dependency fixes and npm lockfile support.
4. Asynchronous API execution so generation requests return a run identifier immediately.
5. Persisted run progress tracking for polling clients.
6. Supabase user authentication, server-side resource ownership, explicit database migrations, and schema readiness checks.

## Operator notes

- Configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and the matching `NEXT_PUBLIC_*` values. Do not configure a service-role key in the web container.
- Run migrations with `alembic upgrade head` before starting the API in production.
- API startup never applies migrations. `/healthz` reports process liveness; `/readyz` returns
  `503` until the database revision matches the Alembic head.
- Artifacts live under `ARTIFACT_ROOT/{run_id}/`. Private downloads require the same authenticated
  owner as the project and run; the browser downloads them with its current access token.
- `ENABLE_DEMO_MODE` defaults to false. Enabling it exposes the separate `/demo/*` fixture workflow without user ownership and should be an explicit deployment decision.
- `PIPELINE_TIMEOUT_SECONDS` bounds each pipeline subprocess (default: 900 seconds).
- Use object storage and a managed worker queue before high-volume usage; the current background task runner is an incremental step, not the final distributed execution architecture.

For Compose, migrate and start as separate operations:

```bash
docker compose --env-file .env.local run --rm migrate
docker compose --env-file .env.local up --build
```
