from __future__ import annotations

import json
from pathlib import Path

from web_api.config import artifact_root


class ArtifactStore:
    """Own run-scoped artifact paths, discovery, and download authorization."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or artifact_root()).resolve()

    def run_directory(self, run_id: str) -> Path:
        path = (self.root / run_id).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid run ID for artifact path")
        return path

    def resolve_file(self, run_id: str, filename: str) -> Path | None:
        run_directory = self.run_directory(run_id)
        path = (run_directory / filename).resolve()
        if path.parent != run_directory or not path.is_file():
            return None
        return path

    def resolve_storage_key(self, storage_key: str) -> Path | None:
        """Resolve a database artifact reference without trusting an absolute path."""
        path = (self.root / storage_key).resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        return path

    def build_result(self, run_id: str, client_slug: str) -> dict:
        directory = self.run_directory(run_id)
        draft_candidates = sorted(directory.glob("agent-4.draft.v*.md"))
        validator = self._read_json(directory / "agent-1.validator.json")
        critic_candidates = sorted(directory.glob("agent-5.critic.v*.json"))
        critic = self._read_json(critic_candidates[-1]) if critic_candidates else {}
        docx = next(directory.glob("*_business_plan.docx"), None)
        pdf = next(directory.glob("*_business_plan.pdf"), None)
        return {
            "run_id": run_id,
            "client_slug": client_slug,
            "draft_file": draft_candidates[-1].name if draft_candidates else None,
            "validation_warnings": {
                "missing_required": validator.get("missing_required", []),
                "thin_fields": validator.get("thin_fields", []),
                "completeness_score": validator.get("completeness_score"),
            },
            "critic": critic,
            "artifact_files": {
                "docx": docx.name if docx else None,
                "pdf": pdf.name if pdf else None,
            },
        }

    def read_text(self, run_id: str, filename: str | None) -> str:
        if not filename:
            return ""
        path = self.resolve_file(run_id, filename)
        return path.read_text(encoding="utf-8") if path else ""

    @staticmethod
    def _read_json(path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return value if isinstance(value, dict) else {}
