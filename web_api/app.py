from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from intake.schema import canonicalize_intake, intake_request_errors
from web_api.artifacts import ArtifactStore, DownloadAuthorizer
from web_api.billing import (
    BillingConfigurationError,
    BillingStore,
    EntitlementUnavailable,
    InvalidWebhook,
    StripeGateway,
)
from web_api.config import PROJECT_ROOT
from web_api.db import RunStore, initial_progress, migration_state
from web_api.execution import ExecutionFailed, ExecutionTimedOut, SubprocessExecutor
from web_api.identity import authenticated_user_id
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
    allow_headers=["Content-Type", "X-API-Key", "X-Authenticated-User-Id"],
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
    owner_id: str = Depends(authenticated_user_id),
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
    try:
        BillingStore().create_paid_run(
            owner_id=owner_id,
            run_id=run_id,
            client_slug=client_slug,
            intake=intake,
            title=str(business_name),
            project_id=req.project_id,
        )
    except EntitlementUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "paid_generation_required",
                "message": "Purchase or release a Funding Ready generation credit first.",
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


@app.get("/runs/{run_id}")
def get_run(
    run_id: str,
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
    owner_id: str = Depends(authenticated_user_id),
) -> dict[str, Any]:
    store = _store()
    run = store.get_owned(run_id, owner_id)
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
        "result": _public_result(run, store.artifacts(run_id)),
        "events": store.events(run_id),
    }


def _public_result(run, artifacts: list) -> dict | None:
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
    authorizer = DownloadAuthorizer()
    payload["exports"] = {
        kind: authorizer.url(run.id, artifact.storage_key.split("/", 1)[-1])
        for kind in ("docx", "pdf")
        if (artifact := by_type.get(kind)) is not None
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
    artifact = _store().artifact_for_filename(run_id, filename)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = _artifact_store().resolve_storage_key(artifact.storage_key)
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path)


@app.get("/billing/package")
def get_package() -> dict[str, Any]:
    return FUNDING_READY.public_dict()


@app.post("/billing/checkout-sessions", status_code=status.HTTP_201_CREATED)
def create_checkout_session(
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
    owner_id: str = Depends(authenticated_user_id),
) -> dict[str, Any]:
    store = BillingStore()
    try:
        payment = store.start_checkout(owner_id)
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
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
    owner_id: str = Depends(authenticated_user_id),
) -> dict[str, Any]:
    store = BillingStore()
    payment = store.get_payment_owned(payment_id, owner_id)
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
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
    owner_id: str = Depends(authenticated_user_id),
) -> dict[str, Any]:
    return BillingStore().entitlement_summary(owner_id)


@app.post("/billing/support-requests", status_code=status.HTTP_201_CREATED)
def create_support_request(
    body: SupportRequestBody,
    _: None = Depends(require_api_key),
    _database: None = Depends(require_database_ready),
    owner_id: str = Depends(authenticated_user_id),
) -> dict[str, Any]:
    try:
        support_request = BillingStore().create_support_request(
            owner_id=owner_id,
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
