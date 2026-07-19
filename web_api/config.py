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
