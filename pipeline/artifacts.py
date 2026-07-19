"""Artifact persistence and run-manifest audit trail."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pipeline.contracts import PipelineResult, RawIntake


@dataclass(frozen=True)
class ArtifactManifest:
    run_id: str
    directory: Path
    files: tuple[Path, ...]


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


class ArtifactService:
    """Persist each record category separately and write one manifest."""

    def write_run(
        self,
        output_dir: Path,
        raw_intake: RawIntake,
        result: PipelineResult,
    ) -> ArtifactManifest:
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[Path] = []

        def write_json(name: str, payload: Any) -> None:
            path = output_dir / name
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
                encoding="utf-8",
            )
            files.append(path)

        def write_text(name: str, payload: str) -> None:
            path = output_dir / name
            path.write_text(payload, encoding="utf-8")
            files.append(path)

        write_json("intake.raw.json", dict(raw_intake.data))
        if result.validation:
            write_json("intake.normalized.json", dict(result.validation.normalized_intake.data))
            write_json("agent-1.validator.json", asdict(result.validation))
        if result.market:
            write_json("agent-2.market.json", asdict(result.market))
            write_text("agent-2.market.md", result.market.narrative)
        if result.financial:
            write_json("agent-3.financial.json", asdict(result.financial))
        for draft in result.draft_history:
            write_text(f"agent-4.draft.v{draft.revision_number}.md", draft.markdown)
        for index, critique in enumerate(result.critique_history):
            write_json(f"agent-5.critic.v{index}.json", asdict(critique))

        write_json("telemetry.json", [asdict(item) for item in result.telemetry])
        write_json("failures.json", [asdict(item) for item in result.failures])
        write_json("progress-events.json", [event.to_dict() for event in result.events])
        manifest_path = output_dir / "run-manifest.json"
        manifest_payload = {
            "run_id": result.run_id,
            "status": result.status.value,
            "files": [path.name for path in files],
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        files.append(manifest_path)
        return ArtifactManifest(result.run_id, output_dir, tuple(files))
