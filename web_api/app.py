from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from intake.schema import canonicalize_intake, intake_request_errors
from web_api.artifacts import ArtifactStore, DownloadAuthorizer
from web_api.config import PROJECT_ROOT
from web_api.db import RunStore, initial_progress, migration_state
from web_api.execution import ExecutionFailed, ExecutionTimedOut, SubprocessExecutor


class GeneratePlanRequest(BaseModel):
    intake: dict[str, Any] = Field(..., description="Business intake payload")


ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app = FastAPI(title="Business Plan Writer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Require X-API-Key when BUSINESS_PLAN_API_KEY is configured."""
    api_key = os.getenv("BUSINESS_PLAN_API_KEY")
    if api_key and (x_api_key is None or not secrets.compare_digest(x_api_key, api_key)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "A valid X-API-Key header is required."},
        )


def require_database_ready() -> None:
    ready, current, expected = migration_state()
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "database_not_ready",
                "message": "Database migrations must be applied before using the API.",
                "current_revision": current,
                "expected_revision": expected,
            },
        )


def _store() -> RunStore:
    return RunStore()


def _artifact_store() -> ArtifactStore:
    return ArtifactStore()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "client"


@app.post("/generate-plan", status_code=status.HTTP_202_ACCEPTED)
def generate_plan(
    req: GeneratePlanRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    intake = canonicalize_intake(req.intake)
    field_errors = intake_request_errors(intake)
    if field_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_intake",
                "message": "Review the highlighted intake fields before generating the plan.",
                "fields": field_errors,
            },
        )

    business_name = intake.get("business_information", {}).get(
        "business_name", "Unknown Business"
    )
    client_slug = _slugify(business_name)
    run_id = str(uuid.uuid4())
    artifact_directory = _artifact_store().run_directory(run_id)
    _store().create(
        run_id=run_id,
        client_slug=client_slug,
        intake=intake,
        artifact_path=str(artifact_directory),
    )

    background_tasks.add_task(_execute_run, run_id)
    return {
        "run_id": run_id,
        "client_slug": client_slug,
        "status": "queued",
        "progress": initial_progress(),
        "status_url": f"/runs/{run_id}",
    }


@app.get("/demo-intake")
def get_demo_intake(_: None = Depends(require_api_key)) -> dict[str, Any]:
    fixture_path = PROJECT_ROOT / "sample_intake" / "fictional_bywater_grounds.json"
    if not fixture_path.is_file():
        raise HTTPException(status_code=404, detail="Demo intake fixture not found.")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _execute_run(run_id: str) -> None:
    store = _store()
    run = store.get(run_id)
    if run is None:
        return
    artifact_store = _artifact_store()
    artifact_directory = artifact_store.run_directory(run_id)
    store.transition(run_id, "running", "Run started.")
    executor = SubprocessExecutor()
    try:
        executor.execute(
            run_id=run_id,
            intake=run.intake_json,
            artifact_directory=artifact_directory,
            on_progress=lambda event: store.record_progress(run_id, event),
        )
        result = artifact_store.build_result(run_id, run.client_slug)
        store.succeed(run_id, result)
    except ExecutionTimedOut as exc:
        store.fail(
            run_id,
            code="pipeline_timeout",
            message="Plan generation took too long and was stopped. Please try again.",
            operator_details=_execution_details(exc.result, str(exc)),
        )
    except ExecutionFailed as exc:
        store.fail(
            run_id,
            code="pipeline_failed",
            message="Plan generation failed. Please review the intake and try again.",
            operator_details=_execution_details(exc.result, str(exc)),
        )
    except Exception as exc:  # noqa: BLE001 - background failures must be persisted
        store.fail(
            run_id,
            code="internal_error",
            message="Plan generation failed unexpectedly. Please try again.",
            operator_details=f"{type(exc).__name__}: {exc}",
        )


def _execution_details(result, message: str) -> str:
    return json.dumps(
        {
            "message": message,
            "return_code": result.return_code,
            "stdout_tail": result.stdout_tail,
            "stderr_tail": result.stderr_tail,
        },
        ensure_ascii=False,
    )


@app.get("/runs/{run_id}")
def get_run(
    run_id: str,
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    store = _store()
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return {
        "run_id": run.id,
        "client_slug": run.client_slug,
        "status": run.status,
        "progress": run.progress_json or [],
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": (
            {"code": run.error_code, "message": run.error_message} if run.error_code else None
        ),
        "result": _public_result(run.result_json),
        "events": store.events(run_id),
    }


def _public_result(result: dict | None) -> dict | None:
    if result is None:
        return None
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"artifact_files", "draft_file"}
    }
    payload["draft_markdown"] = (
        _artifact_store().read_text(result.get("run_id", ""), result.get("draft_file"))
        if "draft_file" in result
        else result.get("draft_markdown", "")
    )
    authorizer = DownloadAuthorizer()
    payload["exports"] = {
        kind: authorizer.url(result["run_id"], filename) if filename else None
        for kind, filename in result.get("artifact_files", {}).items()
    }
    return payload


@app.get("/runs/{run_id}/artifacts/{filename}")
def get_artifact(
    run_id: str,
    filename: str,
    expires: int | None = Query(default=None),
    token: str | None = Query(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    _database: None = Depends(require_database_ready),
) -> FileResponse:
    api_key = os.getenv("BUSINESS_PLAN_API_KEY")
    signed = DownloadAuthorizer(api_key=api_key).authorized(run_id, filename, expires, token)
    header_authorized = bool(
        api_key and x_api_key and secrets.compare_digest(x_api_key, api_key)
    )
    if api_key and not header_authorized and not signed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Artifact authorization is required."},
        )
    run = _store().get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    downloadable = set((run.result_json or {}).get("artifact_files", {}).values())
    if filename not in downloadable:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = _artifact_store().resolve_file(run_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> JSONResponse:
    ready, current, expected = migration_state()
    payload = {
        "status": "ready" if ready else "not_ready",
        "database_revision": current,
        "expected_revision": expected,
    }
    return JSONResponse(payload, status_code=200 if ready else 503)
