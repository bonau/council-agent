"""Tests for preset loading."""

from pathlib import Path

import pytest

from council_agent.config.presets import get_preset_by_name, list_presets

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"


def test_list_presets_finds_both_defaults() -> None:
    presets = list_presets(PRESETS_DIR)
    names = {p.name for p in presets}
    assert names == {"glm-stack", "grok-stack"}


def test_glm_stack_roles() -> None:
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    assert preset.planning.model == "z-ai/glm-5.2"
    assert preset.execution.model == "deepseek/deepseek-v4-flash"
    assert preset.verification.model == "openai/gpt-5.6-luna"
    assert preset.escalation.model == "openai/gpt-5.6-luna"
    assert preset.max_retries == 1


def test_grok_stack_roles() -> None:
    preset = get_preset_by_name(PRESETS_DIR, "grok-stack")
    assert preset.planning.model == "x-ai/grok-4.5"
    assert preset.execution.model == "deepseek/deepseek-v4-flash"
    assert preset.verification.model == "google/gemini-3.5-flash"
    assert preset.escalation.model == "x-ai/grok-4.5"


def test_get_preset_missing_raises() -> None:
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        get_preset_by_name(PRESETS_DIR, "nonexistent")
