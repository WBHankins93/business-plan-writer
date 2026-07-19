"""
helpers for strict JSON agent responses.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from llm_client import LLMClientError, LLMResponse, RetryObserver, call_llm_detailed
from pipeline.contracts import ModelCallTelemetry


class AgentJSONError(ValueError):
    """Raised when an agent response is not valid JSON."""

    def __init__(
        self,
        message: str,
        *,
        raw_response: str = "",
        telemetry: tuple[ModelCallTelemetry, ...] = (),
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.telemetry = telemetry


class AgentContractError(ValueError):
    """Raised when valid JSON does not satisfy an agent's typed contract."""

    def __init__(self, message: str, telemetry: tuple[ModelCallTelemetry, ...]) -> None:
        super().__init__(message)
        self.telemetry = telemetry


@contextmanager
def validate_agent_contract(
    telemetry: tuple[ModelCallTelemetry, ...],
) -> Iterator[None]:
    """Attach completed-call telemetry to downstream contract conversion errors."""
    try:
        yield
    except (KeyError, TypeError, ValueError) as exc:
        raise AgentContractError(str(exc), telemetry) from exc


@dataclass(frozen=True)
class JSONAgentResult:
    data: dict[str, Any]
    telemetry: tuple[ModelCallTelemetry, ...]


def _require_keys(data: dict[str, Any], required_keys: tuple[str, ...]) -> None:
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise AgentJSONError(f"JSON response is missing required keys: {', '.join(missing)}")


def _require_types(data: dict[str, Any], required_types: dict[str, type]) -> None:
    invalid = [
        f"{key} must be {expected.__name__}"
        for key, expected in required_types.items()
        if key in data and not isinstance(data[key], expected)
    ]
    if invalid:
        raise AgentJSONError("; ".join(invalid))


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


def call_json_agent_strict(
    *,
    system_prompt: str,
    user_prompt: str,
    required_keys: tuple[str, ...],
    required_types: dict[str, type] | None = None,
    model: str | None = None,
    temperature: float = 0.3,
    llm_call=call_llm_detailed,
    on_retry: RetryObserver | None = None,
) -> JSONAgentResult:
    """Call a JSON agent with one bounded, non-retrying format correction.

    Provider retries occur only inside the first LLM call. If the response is
    invalid JSON, the correction call gets exactly one provider attempt, which
    prevents provider retries from multiplying across nested repair loops.
    """
    calls: list[ModelCallTelemetry] = []
    first: LLMResponse = llm_call(
        system_prompt,
        user_prompt,
        model=model,
        temperature=temperature,
        on_retry=on_retry,
    )
    calls.append(first.telemetry)
    first_error_message = ""
    try:
        parsed = parse_strict_json(first.text)
        _require_keys(parsed, required_keys)
        _require_types(parsed, required_types or {})
        return JSONAgentResult(parsed, tuple(calls))
    except AgentJSONError as first_error:
        first_error_message = str(first_error)
        repair_prompt = (
            f"{user_prompt}\n\n"
            "Your previous reply was invalid or incomplete JSON. Return one JSON object "
            "with every required key, no markdown, and no commentary."
        )

    try:
        repaired: LLMResponse = llm_call(
            system_prompt,
            repair_prompt,
            model=model,
            temperature=0.0,
            max_attempts=1,
            on_retry=on_retry,
        )
        calls.append(repaired.telemetry)
        parsed = parse_strict_json(repaired.text)
        _require_keys(parsed, required_keys)
        _require_types(parsed, required_types or {})
        return JSONAgentResult(parsed, tuple(calls))
    except (LLMClientError, AgentJSONError) as exc:
        failed_call = getattr(exc, "telemetry", None)
        if isinstance(failed_call, tuple):
            calls.extend(failed_call)
        elif failed_call is not None:
            calls.append(failed_call)
        raise AgentJSONError(
            f"JSON correction failed: {exc}; first response error: {first_error_message}",
            raw_response=first.text,
            telemetry=tuple(calls),
        ) from exc
