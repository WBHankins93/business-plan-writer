"""
helpers for strict JSON agent responses.
"""

from __future__ import annotations

import json
from typing import Any

from llm_client import LLMClientError, call_llm


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


def call_json_agent(
    *,
    system_prompt: str,
    user_prompt: str,
    fallback: dict[str, Any],
    model: str | None = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Call an LLM agent and require JSON, retrying once with stricter instructions."""
    try:
        first = call_llm(system_prompt, user_prompt, model=model, temperature=temperature)
    except LLMClientError as exc:
        return fallback | {"error": {"type": "llm_provider_error", "message": str(exc)}}

    try:
        return parse_strict_json(first)
    except AgentJSONError:
        retry_prompt = (
            f"{user_prompt}\n\n"
            "IMPORTANT: Your previous reply was not valid JSON. "
            "Return valid JSON only, with no markdown or extra text."
        )

    try:
        second = call_llm(system_prompt, retry_prompt, model=model, temperature=0.0)
        return parse_strict_json(second)
    except (LLMClientError, AgentJSONError) as exc:
        return fallback | {
            "error": {"type": "invalid_json_response", "message": str(exc)},
            "raw_response": first,
        }
