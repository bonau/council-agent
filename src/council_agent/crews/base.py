"""Shared utilities for crew output parsing."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_block(text: str) -> dict[str, Any]:
    """Extract a JSON object from agent output, tolerating markdown fences."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in agent output")

    return json.loads(text[start : end + 1])


def crew_output_text(result: object) -> str:
    """Normalize CrewAI kickoff result to plain text."""
    if result is None:
        return ""
    if hasattr(result, "raw"):
        return str(result.raw)
    return str(result)
