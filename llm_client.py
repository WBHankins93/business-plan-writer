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
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

# Load env — .env.local takes precedence over .env
_root = Path(__file__).parent
load_dotenv(_root / ".env.local", override=True)
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
    provider = _PROVIDER_WRITER if writer else _PROVIDER
    resolved_model = model or (_MODEL_WRITER if writer else _MODEL)
    resolved_max_tokens = max_tokens or (8192 if writer else 4096)

    console.log(f"[dim]LLM call → provider={provider} model={resolved_model}[/dim]")

    if provider == "groq":
        return _call_groq(system_prompt, user_prompt, resolved_model, temperature, resolved_max_tokens)
    elif provider == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, resolved_model, temperature, resolved_max_tokens)
    elif provider == "openai":
        return _call_openai(system_prompt, user_prompt, resolved_model, temperature, resolved_max_tokens)
    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}. Must be groq, anthropic, or openai.")


# ── Provider implementations ───────────────────────────────────────────────────

def _call_groq(system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set. Add it to .env.local.")

    try:
        from groq import Groq
    except ImportError:
        raise ImportError("Install the groq package: pip install groq")

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Groq returned empty content.")
    return content


def _call_anthropic(system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Add it to .env.local.")

    try:
        import anthropic
    except ImportError:
        raise ImportError("Install the anthropic package: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=temperature,
    )
    return response.content[0].text


def _call_openai(system_prompt: str, user_prompt: str, model: str, temperature: float, max_tokens: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set. Add it to .env.local.")

    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install the openai package: pip install openai")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned empty content.")
    return content
