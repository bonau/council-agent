"""Preset loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class RoleConfig(BaseModel):
    model: str
    temperature: float = Field(ge=0.0, le=2.0)


class Preset(BaseModel):
    name: str
    description: str
    roles: dict[str, RoleConfig]
    max_retries: int = Field(default=1, ge=0)

    @property
    def planning(self) -> RoleConfig:
        return self.roles["planning"]

    @property
    def execution(self) -> RoleConfig:
        return self.roles["execution"]

    @property
    def verification(self) -> RoleConfig:
        return self.roles["verification"]

    @property
    def escalation(self) -> RoleConfig:
        return self.roles["escalation"]


def load_preset(path: Path) -> Preset:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Preset.model_validate(data)


def list_presets(presets_dir: Path) -> list[Preset]:
    presets: list[Preset] = []
    for path in sorted(presets_dir.glob("*.yaml")):
        presets.append(load_preset(path))
    return presets


def get_preset_by_name(presets_dir: Path, name: str) -> Preset:
    path = presets_dir / f"{name}.yaml"
    if not path.exists():
        available = [p.stem for p in presets_dir.glob("*.yaml")]
        raise FileNotFoundError(
            f"Preset '{name}' not found. Available: {', '.join(available)}"
        )
    return load_preset(path)
