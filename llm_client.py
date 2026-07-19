"""
llm_client.py
Unified LLM provider wrapper for the business plan pipeline.

Providers: groq | anthropic | openai
Config via environment variables:
  LLM_PROVIDER         — provider for standard agents (1, 2, 3, 5)
  LLM_MODEL            — model for standard agents
  LLM_PROVIDER_WRITER  — provider for Agent 4 (plan writer)
  LLM_MODEL_WRITER     — model for Agent 4
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pipeline.contracts import ModelCallTelemetry, ModelUsage

from dotenv import load_dotenv
from rich.console import Console

# Load env — .env.local takes precedence over .env
_root = Path(__file__).parent
load_dotenv(_root / ".env.local", override=False)
load_dotenv(_root / ".env", override=False)

console = Console()

# ── Provider defaults ──────────────────────────────────────────────────────────
_DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
}

# ── Resolved config ────────────────────────────────────────────────────────────
_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
_MODEL = os.getenv("LLM_MODEL") or _DEFAULT_MODELS.get(_PROVIDER, "llama-3.3-70b-versatile")

_PROVIDER_WRITER = os.getenv("LLM_PROVIDER_WRITER", _PROVIDER).lower()
_MODEL_WRITER = os.getenv("LLM_MODEL_WRITER") or _DEFAULT_MODELS.get(_PROVIDER_WRITER, _MODEL)

# Retry / timeout controls
_LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
_LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_LLM_RETRY_BACKOFF_SECONDS = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "1.25"))


class LLMClientError(RuntimeError):
    """Base exception for all LLM client errors."""


class LLMConfigurationError(LLMClientError):
    """Raised when provider/api-key configuration is invalid."""

    def __init__(
        self,
        message: str,
        *,
        telemetry: ModelCallTelemetry | None = None,
    ) -> None:
        super().__init__(message)
        self.telemetry = telemetry


class LLMRequestError(LLMClientError):
    """Raised when a provider request fails after retries."""

    def __init__(
        self,
        message: str,
        *,
        telemetry: ModelCallTelemetry | None = None,
    ) -> None:
        super().__init__(message)
        self.telemetry = telemetry


class LLMTimeoutError(LLMRequestError):
    """Raised when every provider attempt times out."""


@dataclass(frozen=True)
class LLMResponse:
    """Model text plus an auditable call record."""

    text: str
    telemetry: ModelCallTelemetry


@dataclass(frozen=True)
class _ProviderResult:
    text: str
    usage: ModelUsage


RetryObserver = Callable[[int, int, str], None]


def _run_with_retries(
    provider: str,
    model: str,
    operation: Callable[[], _ProviderResult],
    *,
    max_attempts: int,
    on_retry: RetryObserver | None,
    writer: bool,
) -> LLMResponse:
    """
    Run a provider call with bounded retries + backoff.

    Retries are intended for transient provider/network failures.
    """
    last_error: Exception | None = None

    started = time.monotonic()
    all_timeouts = True
    for attempt in range(1, max_attempts + 1):
        try:
            result = operation()
            if not result.text or not result.text.strip():
                raise LLMRequestError(f"{provider} returned an empty response body.")
            duration_ms = round((time.monotonic() - started) * 1000)
            return LLMResponse(
                text=result.text,
                telemetry=ModelCallTelemetry(
                    provider=provider,
                    model=model,
                    duration_ms=duration_ms,
                    attempts=attempt,
                    usage=result.usage,
                    estimated_cost_usd=_estimate_cost(result.usage, writer=writer),
                ),
            )
        except LLMConfigurationError as e:
            duration_ms = round((time.monotonic() - started) * 1000)
            raise LLMConfigurationError(
                str(e),
                telemetry=ModelCallTelemetry(
                    provider=provider,
                    model=model,
                    duration_ms=duration_ms,
                    attempts=attempt,
                    failure_reason=str(e),
                ),
            ) from e
        except TimeoutError as e:
            last_error = e
            is_final = attempt == max_attempts
            if is_final:
                break

            sleep_s = _LLM_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            sleep_s += random.uniform(0.0, 0.25)
            if on_retry:
                on_retry(attempt + 1, max_attempts, f"timeout: {e}")
            console.log(
                f"[yellow]LLM timeout ({provider}) attempt {attempt}/{max_attempts}; "
                f"retrying in {sleep_s:.2f}s[/yellow]"
            )
            time.sleep(sleep_s)
        except Exception as e:  # noqa: BLE001 - provider SDK errors are not uniform
            sdk_timeout = "timeout" in type(e).__name__.lower()
            all_timeouts = all_timeouts and sdk_timeout
            last_error = e
            is_final = attempt == max_attempts
            if is_final:
                break

            sleep_s = _LLM_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            # jitter to reduce request bursts when multiple runs fail simultaneously
            sleep_s += random.uniform(0.0, 0.25)
            if on_retry:
                reason_type = "timeout" if sdk_timeout else "provider_error"
                on_retry(attempt + 1, max_attempts, f"{reason_type}: {e}")
            console.log(
                f"[yellow]LLM {'timeout' if sdk_timeout else 'call failed'} ({provider}) "
                f"attempt {attempt}/{max_attempts}; "
                f"retrying in {sleep_s:.2f}s[/yellow]"
            )
            time.sleep(sleep_s)

    error_type = LLMTimeoutError if all_timeouts else LLMRequestError
    duration_ms = round((time.monotonic() - started) * 1000)
    message = f"{provider} request failed after {max_attempts} attempts: {last_error}"
    raise error_type(
        message,
        telemetry=ModelCallTelemetry(
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            attempts=max_attempts,
            failure_reason=str(last_error),
        ),
    ) from last_error


def _estimate_cost(usage: ModelUsage, *, writer: bool) -> float | None:
    """Estimate cost from configurable per-million-token rates when usage exists."""
    prefix = "LLM_WRITER" if writer else "LLM"
    input_rate = os.getenv(f"{prefix}_INPUT_COST_PER_MILLION_USD")
    output_rate = os.getenv(f"{prefix}_OUTPUT_COST_PER_MILLION_USD")
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    if input_rate is None or output_rate is None:
        return None
    try:
        cost = (
            usage.input_tokens * float(input_rate)
            + usage.output_tokens * float(output_rate)
        ) / 1_000_000
    except ValueError:
        return None
    return round(cost, 8)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    writer: bool = False,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    """
    Call the configured LLM provider and return the response text.

    Args:
        system_prompt: The system/identity prompt for the agent.
        user_prompt:   The task or question for this call.
        writer:        If True, use the writer provider/model (Agent 4).
        model:         Explicit model override (ignores env config).
        temperature:   Sampling temperature (default 0.7).
        max_tokens:    Max output tokens. Writer agents default to 8192;
                       standard agents default to 4096.

    Returns:
        The model's response as a string.
    """
    return call_llm_detailed(
        system_prompt,
        user_prompt,
        writer=writer,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    ).text


def call_llm_detailed(
    system_prompt: str,
    user_prompt: str,
    *,
    writer: bool = False,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    max_attempts: int | None = None,
    on_retry: RetryObserver | None = None,
) -> LLMResponse:
    """Call one model and return text, usage, timing, cost, and attempt metadata.

    This function is the sole provider-retry owner. Callers that perform a JSON
    correction pass must set ``max_attempts=1`` for that correction call.
    """
    provider = _PROVIDER_WRITER if writer else _PROVIDER
    resolved_model = model or (_MODEL_WRITER if writer else _MODEL)
    resolved_max_tokens = max_tokens or (8192 if writer else 4096)
    resolved_attempts = _LLM_MAX_RETRIES if max_attempts is None else max_attempts
    if resolved_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    console.log(f"[dim]LLM call → provider={provider} model={resolved_model}[/dim]")

    if provider == "groq":
        return _run_with_retries(
            provider,
            resolved_model,
            lambda: _call_groq(system_prompt, user_prompt, resolved_model, temperature, resolved_max_tokens),
            max_attempts=resolved_attempts,
            on_retry=on_retry,
            writer=writer,
        )
    elif provider == "anthropic":
        return _run_with_retries(
            provider,
            resolved_model,
            lambda: _call_anthropic(system_prompt, user_prompt, resolved_model, temperature, resolved_max_tokens),
            max_attempts=resolved_attempts,
            on_retry=on_retry,
            writer=writer,
        )
    elif provider == "openai":
        return _run_with_retries(
            provider,
            resolved_model,
            lambda: _call_openai(system_prompt, user_prompt, resolved_model, temperature, resolved_max_tokens),
            max_attempts=resolved_attempts,
            on_retry=on_retry,
            writer=writer,
        )
    else:
        raise LLMConfigurationError(
            f"Unknown LLM provider: {provider!r}. Must be groq, anthropic, or openai.",
            telemetry=ModelCallTelemetry(
                provider=provider,
                model=resolved_model,
                duration_ms=0,
                attempts=0,
                failure_reason="unknown provider",
            ),
        )


# ── Provider implementations ───────────────────────────────────────────────────

def _usage(input_tokens: int | None, output_tokens: int | None, total_tokens: int | None) -> ModelUsage:
    return ModelUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


def _call_groq(system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int) -> _ProviderResult:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMConfigurationError("GROQ_API_KEY is not set. Add it to .env.local.")

    try:
        from groq import Groq
    except ImportError:
        raise LLMConfigurationError("Install the groq package: pip install groq")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=_LLM_TIMEOUT_SECONDS,
    )
    content = response.choices[0].message.content
    if content is None:
        raise LLMRequestError("Groq returned empty content.")
    usage = getattr(response, "usage", None)
    return _ProviderResult(
        text=content,
        usage=_usage(
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            getattr(usage, "total_tokens", None),
        ),
    )


def _call_anthropic(system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int) -> _ProviderResult:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMConfigurationError("ANTHROPIC_API_KEY is not set. Add it to .env.local.")

    try:
        import anthropic
    except ImportError:
        raise LLMConfigurationError("Install the anthropic package: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key, timeout=_LLM_TIMEOUT_SECONDS)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=temperature,
    )
    if not response.content or not getattr(response.content[0], "text", None):
        raise LLMRequestError("Anthropic returned empty content.")
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    return _ProviderResult(
        text=response.content[0].text,
        usage=_usage(input_tokens, output_tokens, total_tokens),
    )


def _call_openai(system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int) -> _ProviderResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMConfigurationError("OPENAI_API_KEY is not set. Add it to .env.local.")

    try:
        from openai import OpenAI
    except ImportError:
        raise LLMConfigurationError("Install the openai package: pip install openai")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=_LLM_TIMEOUT_SECONDS,
    )
    content = response.choices[0].message.content
    if content is None:
        raise LLMRequestError("OpenAI returned empty content.")
    usage = getattr(response, "usage", None)
    return _ProviderResult(
        text=content,
        usage=_usage(
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            getattr(usage, "total_tokens", None),
        ),
    )
