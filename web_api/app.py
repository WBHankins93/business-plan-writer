from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from web_api.db import SessionLocal
from web_api.models import Run


class GeneratePlanRequest(BaseModel):
    intake: dict[str, Any] = Field(..., description="Business intake payload")


API_KEY = os.getenv("BUSINESS_PLAN_API_KEY")
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


PIPELINE_STEPS = [
    {"step": 1, "name": "Validation"},
    {"step": 2, "name": "Market"},
    {"step": 3, "name": "Financials"},
    {"step": 4, "name": "Draft"},
    {"step": 5, "name": "Review"},
]


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Require X-API-Key when BUSINESS_PLAN_API_KEY is configured."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "A valid X-API-Key header is required."},
        )


def _session() -> Session:
    return SessionLocal()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "client"


def _progress(status_value: str) -> list[dict[str, Any]]:
    return [{**step, "status": status_value} for step in PIPELINE_STEPS]


@app.post("/generate-plan", status_code=status.HTTP_202_ACCEPTED)
def generate_plan(
    req: GeneratePlanRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    intake = req.intake
    business_name = intake.get("business_information", {}).get("business_name", "Unknown Business")
    client_slug = _slugify(business_name)

    db = _session()
    try:
        run = Run(
            client_slug=client_slug,
            status="queued",
            intake_json=intake,
            progress_json=_progress("pending"),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    finally:
        db.close()

    background_tasks.add_task(_execute_run, run_id)
    return {
        "run_id": run_id,
        "client_slug": client_slug,
        "status": "queued",
        "progress": _progress("pending"),
        "status_url": f"/runs/{run_id}",
    }


def _execute_run(run_id: str) -> None:
    db = _session()
    try:
        run = db.scalar(select(Run).where(Run.id == run_id))
        if not run:
            return

        run.status = "running"
        run.progress_json = _progress("running")
        db.add(run)
        db.commit()

        intake = run.intake_json
        client_slug = run.client_slug
        artifact_dir = Path("output") / client_slug
        artifact_dir.mkdir(parents=True, exist_ok=True)
        intake_path = artifact_dir / f"web_intake_{run.id}.json"
        intake_path.write_text(json.dumps(intake, indent=2, ensure_ascii=False), encoding="utf-8")

        cmd = [
            sys.executable,
            "main.py",
            "--intake",
            str(intake_path),
            "--output-dir",
            str(artifact_dir),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            run.status = "failed"
            run.progress_json = _progress("failed")
            run.error_text = f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
            db.add(run)
            db.commit()
            return

        response = _build_run_response(run.id, client_slug, artifact_dir)
        run.status = "succeeded"
        run.progress_json = response["progress"]
        run.result_json = response
        run.error_text = None
        db.add(run)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - background task must persist unexpected failures
        run = db.scalar(select(Run).where(Run.id == run_id))
        if run:
            run.status = "failed"
            run.progress_json = _progress("failed")
            run.error_text = str(exc)
            db.add(run)
            db.commit()
    finally:
        db.close()


def _build_run_response(run_id: str, client_slug: str, artifact_dir: Path) -> dict[str, Any]:
    revised_path = artifact_dir / "business_plan_revised.md"
    draft_path = revised_path if revised_path.exists() else artifact_dir / "raw_agent_4.md"
    draft_markdown = draft_path.read_text(encoding="utf-8") if draft_path.exists() else ""
    agent_1 = _read_json_if_present(artifact_dir / "raw_agent_1.json")
    agent_5 = _read_json_if_present(artifact_dir / "raw_agent_5.json")
    critique = agent_5.get("critique", {})
    a1_report = agent_1.get("agent_1_report", {})
    output_docx = next(artifact_dir.glob("*_business_plan.docx"), None)
    output_pdf = next(artifact_dir.glob("*_business_plan.pdf"), None)

    return {
        "run_id": run_id,
        "client_slug": client_slug,
        "status": "succeeded",
        "progress": _progress("complete"),
        "draft_markdown": draft_markdown,
        "artifact_dir": str(artifact_dir),
        "validation_warnings": {
            "missing_required": a1_report.get("missing_required", []),
            "thin_fields": a1_report.get("thin_fields", []),
            "completeness_score": a1_report.get("completeness_score"),
        },
        "critic": critique,
        "exports": {
            "docx": f"/artifacts/{client_slug}/{output_docx.name}" if output_docx else None,
            "pdf": f"/artifacts/{client_slug}/{output_pdf.name}" if output_pdf else None,
        },
    }


@app.get("/artifacts/{client_slug}/{filename}")
def get_artifact(
    client_slug: str,
    filename: str,
    _: None = Depends(require_api_key),
) -> FileResponse:
    path = Path("output") / client_slug / filename
    output_root = Path("output").resolve()
    resolved_path = path.resolve()
    if output_root not in resolved_path.parents or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(resolved_path)


@app.get("/runs/{run_id}")
def get_run(run_id: str, _: None = Depends(require_api_key)) -> dict[str, Any]:
    db = _session()
    try:
        run = db.scalar(select(Run).where(Run.id == run_id))
        if not run:
            raise HTTPException(status_code=404, detail="Run not found.")
        return {
            "run_id": run.id,
            "client_slug": run.client_slug,
            "status": run.status,
            "progress": run.progress_json or [],
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "error": run.error_text,
            "result": run.result_json,
        }
    finally:
        db.close()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    db = _session()
    try:
        db.execute(select(1))
        return {"status": "ready"}
    finally:
        db.close()


def _read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
