from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from intake.schema import canonicalize_intake, intake_request_errors
from web_api.artifacts import ArtifactStore
from web_api.billing import (
    BillingConfigurationError,
    BillingStore,
    EntitlementUnavailable,
    InvalidWebhook,
    StripeGateway,
)
from web_api.auth import AuthenticatedUser, require_user
from web_api.config import PROJECT_ROOT, generation_configuration
from web_api.db import (
    IntakeDraftStore,
    ProfileStore,
    ProjectStore,
    RunStore,
    initial_progress,
    migration_state,
)
from web_api.execution import ExecutionFailed, ExecutionTimedOut, SubprocessExecutor
from web_api.packages import FUNDING_READY


class GeneratePlanRequest(BaseModel):
    intake: dict[str, Any] = Field(..., description="Business intake payload")
    project_id: str | None = Field(default=None, max_length=36)


class SupportRequestBody(BaseModel):
    client_request_id: str = Field(..., min_length=1, max_length=100)
    kind: Literal["payment", "refund", "generation", "human_qa", "other"]
    message: str = Field(..., min_length=10, max_length=4000)
    payment_id: str | None = Field(default=None, max_length=36)
    run_id: str | None = Field(default=None, max_length=36)


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


def _draft_store() -> IntakeDraftStore:
    return IntakeDraftStore()


def _artifact_store() -> ArtifactStore:
    return ArtifactStore()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "client"


def _project_payload(project) -> dict[str, Any]:
    draft = _draft_store().get_owned(project.id, project.owner_id)
    return {
        "id": project.id,
        "title": project.title,
        "intake": draft.data_json if draft else {},
        "current_step": draft.current_step if draft else 0,
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
    draft = _draft_store().save_owned(
        project_id=project_id,
        owner_id=user.id,
        data=intake,
        current_step=req.current_step,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    project = _owned_project_or_404(project_id, user)
    return _project_payload(project)


@app.post("/projects/{project_id}/generate-plan", status_code=status.HTTP_202_ACCEPTED)
def generate_project_plan(
    project_id: str,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    project = _owned_project_or_404(project_id, user)
    draft = _draft_store().get_owned(project.id, user.id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "missing_intake", "message": "Save the intake before generating."},
        )
    return _queue_plan(
        intake=draft.data_json,
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
    if owner_id is None:
        provider, model, configuration = generation_configuration()
        _store().create(
            run_id=run_id,
            client_slug=client_slug,
            intake=canonical,
            provider=provider,
            model=model,
            configuration=configuration,
        )
    else:
        try:
            BillingStore().create_paid_run(
                owner_id=owner_id,
                run_id=run_id,
                client_slug=client_slug,
                intake=canonical,
                title=str(business_name),
                project_id=project_id,
            )
        except EntitlementUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "code": "paid_generation_required",
                    "message": "Purchase or release a Funding-Focused generation credit first.",
                    "checkout_url": "/billing/checkout-sessions",
                },
            ) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Project not found.") from exc
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
            intake=run.input_snapshot_json,
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
        "result": _public_result(
            run,
            _store().artifacts(run.id),
            export_prefix=export_prefix,
        ),
        "events": _store().events(run.id),
    }


def _public_result(run, artifacts: list, *, export_prefix: str) -> dict | None:
    result = run.output_summary_json
    if result is None:
        return None
    payload = dict(result)
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}
    draft = by_type.get("draft")
    payload["draft_markdown"] = result.get("draft_markdown", "")
    if draft is not None and draft.storage_provider == "filesystem":
        path = _artifact_store().resolve_storage_key(draft.storage_key)
        payload["draft_markdown"] = path.read_text(encoding="utf-8") if path else ""
    payload["exports"] = {
        kind: f"{export_prefix}/{artifact.storage_key.split('/', 1)[-1]}"
        for kind in ("docx", "pdf")
        if (artifact := by_type.get(kind)) is not None
    }
    return payload


def _artifact_response(run, run_id: str, filename: str) -> FileResponse:
    if run is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    artifact = _store().artifact_for_filename(run_id, filename)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = _artifact_store().resolve_storage_key(artifact.storage_key)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path, filename=filename)


@app.get("/billing/package")
def get_package() -> dict[str, Any]:
    return FUNDING_READY.public_dict()


@app.post("/billing/checkout-sessions", status_code=status.HTTP_201_CREATED)
def create_checkout_session(
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    ProfileStore().create(user.id)
    store = BillingStore()
    try:
        payment = store.start_checkout(user.id)
    except (BillingConfigurationError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail={"code": "billing_not_configured"}) from exc
    if payment is None:
        raise HTTPException(status_code=409, detail={"code": "profile_not_ready"})
    try:
        checkout = StripeGateway().create_checkout_session(
            payment_id=payment.id, package=FUNDING_READY
        )
        store.attach_checkout(payment.id, checkout)
    except BillingConfigurationError as exc:
        store.fail_checkout_creation(payment.id, str(exc))
        raise HTTPException(status_code=503, detail={"code": "billing_not_configured"}) from exc
    except Exception as exc:  # Stripe failures are persisted without leaking provider details.
        store.fail_checkout_creation(payment.id, f"{type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail={"code": "checkout_unavailable", "message": "Checkout is temporarily unavailable."},
        ) from exc
    return {
        "payment_id": payment.id,
        "payment_status": "checkout_pending",
        "checkout_url": checkout.url,
        "status_url": f"/billing/payments/{payment.id}",
    }


@app.get("/billing/payments/{payment_id}")
def get_payment_status(
    payment_id: str,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    store = BillingStore()
    payment = store.get_payment_owned(payment_id, user.id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    entitlement = store.entitlement_for_payment(payment.id)
    return {
        "payment_id": payment.id,
        "package_code": payment.package_code,
        "payment_status": payment.status,
        "entitlement": (
            {
                "id": entitlement.id,
                "status": entitlement.status,
                "revision_limit": entitlement.revision_limit,
                "revisions_used": entitlement.revisions_used,
            }
            if entitlement
            else None
        ),
    }


@app.get("/billing/entitlements")
def get_entitlements(
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    return BillingStore().entitlement_summary(user.id)


@app.post("/billing/support-requests", status_code=status.HTTP_201_CREATED)
def create_support_request(
    body: SupportRequestBody,
    user: AuthenticatedUser = Depends(require_user),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    try:
        support_request = BillingStore().create_support_request(
            owner_id=user.id,
            client_request_id=body.client_request_id,
            kind=body.kind,
            message=body.message,
            payment_id=body.payment_id,
            run_id=body.run_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "support_request_id": support_request.id,
        "status": support_request.status,
        "kind": support_request.kind,
    }


@app.post("/billing/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    _database: None = Depends(require_database_ready),
) -> dict[str, Any]:
    payload = await request.body()
    try:
        event = StripeGateway().construct_event(payload, stripe_signature)
    except InvalidWebhook as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_signature"}) from exc
    except BillingConfigurationError as exc:
        raise HTTPException(status_code=503, detail={"code": "billing_not_configured"}) from exc
    return BillingStore().process_event(event)


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
