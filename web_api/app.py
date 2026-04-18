from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


class GeneratePlanRequest(BaseModel):
    intake: dict[str, Any] = Field(..., description="Business intake payload")


app = FastAPI(title="Business Plan Writer API")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "client"


@app.post("/generate-plan")
def generate_plan(req: GeneratePlanRequest) -> dict[str, Any]:
    intake = req.intake
    business_name = intake.get("business_information", {}).get("business_name", "Unknown Business")
    client_slug = _slugify(business_name)

    artifact_dir = Path("output") / client_slug
    artifact_dir.mkdir(parents=True, exist_ok=True)
    intake_path = artifact_dir / "web_intake.json"
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
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Pipeline execution failed.",
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
            },
        )

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
        "client_slug": client_slug,
        "progress": [
            {"step": 1, "name": "Validation", "status": "complete"},
            {"step": 2, "name": "Market", "status": "complete"},
            {"step": 3, "name": "Financials", "status": "complete"},
            {"step": 4, "name": "Draft", "status": "complete"},
            {"step": 5, "name": "Review", "status": "complete"},
        ],
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
def get_artifact(client_slug: str, filename: str) -> FileResponse:
    path = Path("output") / client_slug / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path)


def _read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
