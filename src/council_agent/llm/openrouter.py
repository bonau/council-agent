"""OpenRouter LLM factory for CrewAI."""

from __future__ import annotations

from dataclasses import dataclass, field

from crewai import LLM

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class OpenRouterCredential:
    """Provider-only API credential with a non-revealing representation."""

    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("OpenRouter API key must be a non-empty string")

    def get_secret_value(self) -> str:
        """Reveal the provider key only at the model-client boundary."""

        return self.api_key

    def __repr__(self) -> str:
        return "OpenRouterCredential(api_key='[REDACTED]')"


def make_llm(
    model: str,
    temperature: float,
    credential: OpenRouterCredential,
) -> LLM:
    """Create a CrewAI LLM instance routed through OpenRouter."""
    if not isinstance(credential, OpenRouterCredential):
        raise TypeError("credential must be an OpenRouterCredential")
    model_id = model if model.startswith("openrouter/") else f"openrouter/{model}"
    return LLM(
        model=model_id,
        base_url=OPENROUTER_BASE_URL,
        api_key=credential.get_secret_value(),
        temperature=temperature,
    )
