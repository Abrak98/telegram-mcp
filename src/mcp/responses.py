"""Response formatting utilities."""

import json
from typing import Any

DEFAULT_CHAR_LIMIT = 8000
MAX_CHAR_LIMIT = 20000


def json_response(data: Any) -> str:
    """Format data as JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def error_response(error: str, hint: str | None = None) -> str:
    """Format error as JSON."""
    data = {"error": error}
    if hint:
        data["hint"] = hint
    return json_response(data)


def truncate(text: str, limit: int = DEFAULT_CHAR_LIMIT) -> str:
    """Truncate text with notice if exceeds limit."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [truncated, {len(text) - limit} chars more]"
