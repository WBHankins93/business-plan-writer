from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from intake.schema import canonicalize_intake, intake_request_errors
from web_api.artifacts import ArtifactStore
from web_api.auth import AuthenticatedUser, require_user
from web_api.config import PROJECT_ROOT
from web_api.db import ProjectStore, RunStore, initial_progress, migration_state
from web_api.execution import ExecutionFailed, ExecutionTimedOut, SubprocessExecutor


class GeneratePlanRequest(BaseModel):
    intake: dict[str, Any] = Field(..., description="Business intake payload")


class SaveDraftRequest(BaseModel):
    intake: dict[str, Any] = Field(..., description="Current business intake draft")
    current_step: int = Field(default=0, ge=0, le=4)


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
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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


def require_demo_enabled() -> None:
    if os.getenv("ENABLE_DEMO_MODE", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=404, detail="Demo mode is not enabled.")


def _store() -> RunStore:
    return RunStore()


def _project_store() -> ProjectStore:
    return ProjectStore()


def _artifact_store() -> ArtifactStore:
    return ArtifactStore()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "client"


def _project_payload(project) -> dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "intake": project.intake_json or {},
        "current_step": project.current_step,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


def _project_summary_payload(project) -> dict[str, Any]:
    payload = _project_payload(project)
    payload.pop("intake")
    return payload


def _owned_project_or_404(project_id: str, user: AuthenticatedUser):
    project = _project_store().get_owned(project_id, user.id)
    if project is None:
        # A 404 avoids disclosing whether another user owns this identifier.
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@app.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    return _project_payload(_project_store().create(user.id))


@app.get("/projects")
def list_projects(
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> list[dict[str, Any]]:
    return [_project_summary_payload(project) for project in _project_store().list_owned(user.id)]


@app.get("/projects/{project_id}")
def get_project(
    project_id: str,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    return _project_payload(_owned_project_or_404(project_id, user))


@app.put("/projects/{project_id}/draft")
def save_project_draft(
    project_id: str,
    req: SaveDraftRequest,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    intake = canonicalize_intake(req.intake)
    project = _project_store().update_draft(
        project_id=project_id,
        owner_id=user.id,
        intake=intake,
        current_step=req.current_step,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return _project_payload(project)


@app.post("/projects/{project_id}/generate-plan", status_code=status.HTTP_202_ACCEPTED)
def generate_project_plan(
    project_id: str,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    project = _owned_project_or_404(project_id, user)
    return _queue_plan(
        intake=project.intake_json,
        background_tasks=background_tasks,
        owner_id=user.id,
        project_id=project.id,
        status_prefix="/runs",
    )


@app.get("/runs/{run_id}")
def get_run(
    run_id: str,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    run = _store().get_owned(run_id, user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_payload(run, export_prefix=f"/runs/{run.id}/artifacts")


@app.get("/runs/{run_id}/artifacts/{filename}")
def get_artifact(
    run_id: str,
    filename: str,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> FileResponse:
    run = _store().get_owned(run_id, user.id)
    return _artifact_response(run, run_id, filename)


@app.get("/demo/intake", dependencies=[Depends(require_demo_enabled)])
def get_demo_intake() -> dict[str, Any]:
    fixture_path = PROJECT_ROOT / "sample_intake" / "fictional_bywater_grounds.json"
    if not fixture_path.is_file():
        raise HTTPException(status_code=404, detail="Demo intake fixture not found.")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@app.post(
    "/demo/generate-plan",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_demo_enabled), Depends(require_database_ready)],
)
def generate_demo_plan(
    req: GeneratePlanRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    return _queue_plan(
        intake=req.intake,
        background_tasks=background_tasks,
        owner_id=None,
        project_id=None,
        status_prefix="/demo/runs",
    )


@app.get(
    "/demo/runs/{run_id}",
    dependencies=[Depends(require_demo_enabled), Depends(require_database_ready)],
)
def get_demo_run(run_id: str) -> dict[str, Any]:
    run = _store().get_demo(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Demo run not found.")
    return _run_payload(run, export_prefix=f"/demo/runs/{run.id}/artifacts")


@app.get(
    "/demo/runs/{run_id}/artifacts/{filename}",
    dependencies=[Depends(require_demo_enabled), Depends(require_database_ready)],
)
def get_demo_artifact(run_id: str, filename: str) -> FileResponse:
    return _artifact_response(_store().get_demo(run_id), run_id, filename)


def _queue_plan(
    *,
    intake: dict[str, Any],
    background_tasks: BackgroundTasks,
    owner_id: str | None,
    project_id: str | None,
    status_prefix: str,
) -> dict[str, Any]:
    canonical = canonicalize_intake(intake)
    field_errors = intake_request_errors(canonical)
    if field_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_intake",
                "message": "Review the highlighted intake fields before generating the plan.",
                "fields": field_errors,
            },
        )

    business_name = canonical.get("business_information", {}).get(
        "business_name", "Unknown Business"
    )
    client_slug = _slugify(business_name)
    run_id = str(uuid.uuid4())
    artifact_directory = _artifact_store().run_directory(run_id)
    _store().create(
        run_id=run_id,
        client_slug=client_slug,
        intake=canonical,
        artifact_path=str(artifact_directory),
        owner_id=owner_id,
        project_id=project_id,
    )
    background_tasks.add_task(_execute_run, run_id)
    return {
        "run_id": run_id,
        "client_slug": client_slug,
        "status": "queued",
        "progress": initial_progress(),
        "status_url": f"{status_prefix}/{run_id}",
    }


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


def _run_payload(run, *, export_prefix: str) -> dict[str, Any]:
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
        "result": _public_result(run.result_json, export_prefix=export_prefix),
        "events": _store().events(run.id),
    }


def _public_result(result: dict | None, *, export_prefix: str) -> dict | None:
    if result is None:
        return None
    payload = {
        key: value for key, value in result.items() if key not in {"artifact_files", "draft_file"}
    }
    payload["draft_markdown"] = (
        _artifact_store().read_text(result.get("run_id", ""), result.get("draft_file"))
        if "draft_file" in result
        else result.get("draft_markdown", "")
    )
    payload["exports"] = {
        kind: f"{export_prefix}/{filename}" if filename else None
        for kind, filename in result.get("artifact_files", {}).items()
    }
    return payload


def _artifact_response(run, run_id: str, filename: str) -> FileResponse:
    if run is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    downloadable = set((run.result_json or {}).get("artifact_files", {}).values())
    if filename not in downloadable:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = _artifact_store().resolve_file(run_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path, filename=filename)


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
