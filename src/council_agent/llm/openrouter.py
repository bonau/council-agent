"""OpenRouter LLM factory for CrewAI."""

from __future__ import annotations

from crewai import LLM

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def make_llm(model: str, temperature: float, api_key: str) -> LLM:
    """Create a CrewAI LLM instance routed through OpenRouter."""
    model_id = model if model.startswith("openrouter/") else f"openrouter/{model}"
    return LLM(
        model=model_id,
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        temperature=temperature,
    )
