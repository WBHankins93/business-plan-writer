from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

from web_api.config import artifact_root, download_token_ttl_seconds


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


class DownloadAuthorizer:
    """Create short-lived links so browser downloads can use API-key protection."""

    def __init__(self, api_key: str | None = None, ttl_seconds: int | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("BUSINESS_PLAN_API_KEY")
        self.ttl_seconds = ttl_seconds or download_token_ttl_seconds()

    def url(self, run_id: str, filename: str) -> str:
        base = f"/runs/{quote(run_id, safe='')}/artifacts/{quote(filename, safe='')}"
        if not self.api_key:
            return base
        expires = int(time.time()) + self.ttl_seconds
        token = self._signature(run_id, filename, expires)
        return f"{base}?expires={expires}&token={token}"

    def authorized(self, run_id: str, filename: str, expires: int | None, token: str | None) -> bool:
        if not self.api_key:
            return True
        if expires is None or token is None or expires < int(time.time()):
            return False
        expected = self._signature(run_id, filename, expires)
        return hmac.compare_digest(expected, token)

    def _signature(self, run_id: str, filename: str, expires: int) -> str:
        assert self.api_key is not None
        payload = f"{run_id}\n{filename}\n{expires}".encode()
        return hmac.new(self.api_key.encode(), payload, hashlib.sha256).hexdigest()
