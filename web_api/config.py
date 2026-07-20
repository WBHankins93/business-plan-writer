from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Local development uses .env.local; real process environment always wins.
load_dotenv(PROJECT_ROOT / ".env.local", override=False)
load_dotenv(PROJECT_ROOT / ".env", override=False)


def database_url() -> str:
    default_path = (PROJECT_ROOT / "output" / "business_plan_writer.db").as_posix()
    return os.getenv("DATABASE_URL", f"sqlite:///{default_path}")


def artifact_root() -> Path:
    configured = os.getenv("ARTIFACT_ROOT")
    return Path(configured).resolve() if configured else PROJECT_ROOT / "output" / "runs"


def pipeline_timeout_seconds() -> float:
    raw_value = os.getenv("PIPELINE_TIMEOUT_SECONDS", "900")
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError("PIPELINE_TIMEOUT_SECONDS must be a number") from exc
    if value <= 0:
        raise RuntimeError("PIPELINE_TIMEOUT_SECONDS must be greater than zero")
    return value


def download_token_ttl_seconds() -> int:
    raw_value = os.getenv("DOWNLOAD_TOKEN_TTL_SECONDS", "900")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("DOWNLOAD_TOKEN_TTL_SECONDS must be an integer") from exc
    if value <= 0:
        raise RuntimeError("DOWNLOAD_TOKEN_TTL_SECONDS must be greater than zero")
    return value


def generation_configuration() -> tuple[str, str, dict[str, object]]:
    """Return the non-secret model configuration snapshotted with a new run."""
    default_models = {
        "groq": "llama-3.3-70b-versatile",
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
    }
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL") or default_models.get(
        provider, "llama-3.3-70b-versatile"
    )
    writer_provider = os.getenv("LLM_PROVIDER_WRITER", provider).lower()
    writer_model = os.getenv("LLM_MODEL_WRITER") or default_models.get(
        writer_provider, model
    )
    configuration: dict[str, object] = {
        "writer_provider": writer_provider,
        "writer_model": writer_model,
        "timeout_seconds": float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        "max_attempts": int(os.getenv("LLM_MAX_RETRIES", "3")),
    }
    return provider, model, configuration


def funding_ready_price_cents() -> int:
    raw_value = os.getenv("FUNDING_READY_PRICE_CENTS", "75000")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("FUNDING_READY_PRICE_CENTS must be an integer") from exc
    if value <= 0:
        raise RuntimeError("FUNDING_READY_PRICE_CENTS must be greater than zero")
    return value


def funding_ready_currency() -> str:
    value = os.getenv("FUNDING_READY_CURRENCY", "usd").strip().lower()
    if len(value) != 3 or not value.isalpha():
        raise RuntimeError("FUNDING_READY_CURRENCY must be a three-letter currency code")
    return value


def stripe_secret_key() -> str:
    value = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not value:
        raise RuntimeError("STRIPE_SECRET_KEY is required for checkout")
    if value.startswith("sk_live_") and os.getenv("STRIPE_ALLOW_LIVE_MODE", "").lower() != "true":
        raise RuntimeError("Set STRIPE_ALLOW_LIVE_MODE=true before using a live Stripe key")
    return value


def stripe_webhook_secret() -> str:
    value = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not value:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is required for webhook verification")
    return value


def checkout_success_url() -> str:
    return os.getenv(
        "STRIPE_CHECKOUT_SUCCESS_URL", "http://localhost:3000/?checkout=success"
    ).strip()


def checkout_cancel_url() -> str:
    return os.getenv(
        "STRIPE_CHECKOUT_CANCEL_URL", "http://localhost:3000/?checkout=canceled"
    ).strip()
