"""
Utilities for building token-conscious prompts.
"""

from __future__ import annotations

import json
from typing import Any


def compact_json(data: Any, max_chars: int = 12000) -> str:
    """
    Serialize JSON with defensive truncation for prompt size control.
    """
    text = json.dumps(data, indent=2, default=str)
    return truncate_text(text, max_chars=max_chars)


def truncate_text(text: str, max_chars: int = 12000) -> str:
    """
    Truncate text while preserving the beginning and end for context.
    """
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.75)
    tail = max_chars - head
    return (
        f"{text[:head]}\n\n...[TRUNCATED {len(text) - max_chars} chars]...\n\n"
        f"{text[-tail:]}"
    )

