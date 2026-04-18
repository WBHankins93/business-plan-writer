"""
helpers for strict JSON agent responses.
"""

from __future__ import annotations

import json
from typing import Any


class AgentJSONError(ValueError):
    """Raised when an agent response is not valid JSON."""


def parse_strict_json(raw: str) -> dict[str, Any]:
    """Parse an agent response as strict JSON (supports fenced blocks)."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise AgentJSONError(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AgentJSONError("JSON response must be an object.")
    return parsed

