"""`.council/config.yaml` schema, loader, and workspace resolution."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from council_agent.config.settings import get_settings
from council_agent.sandbox.workspace import get_workspace_guard


class CouncilConfig(BaseModel):
    """Project-level sandbox configuration stored under `.council/`."""

    workspace_root: str
    denied_patterns: list[str] = Field(default_factory=list)


def council_dir(project_root: Path) -> Path:
    return Path(project_root) / ".council"


def config_path(project_root: Path) -> Path:
    return council_dir(project_root) / "config.yaml"


def sessions_dir(project_root: Path) -> Path:
    return council_dir(project_root) / "sessions"


def is_sandbox_initialized(project_root: Path) -> bool:
    return config_path(project_root).is_file()


def load_council_config(project_root: Path) -> CouncilConfig:
    path = config_path(project_root)
    if not path.is_file():
        raise FileNotFoundError(f"Sandbox config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CouncilConfig.model_validate(data)


def write_council_config(project_root: Path, config: CouncilConfig) -> None:
    council = council_dir(project_root)
    council.mkdir(parents=True, exist_ok=True)
    sessions_dir(project_root).mkdir(parents=True, exist_ok=True)
    payload = config.model_dump()
    config_path(project_root).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def init_sandbox(project_root: Path) -> CouncilConfig:
    """Create `.council/` idempotently; never delete existing sessions."""
    root = Path(project_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    sessions_dir(root).mkdir(parents=True, exist_ok=True)

    path = config_path(root)
    if path.is_file():
        existing = load_council_config(root)
        # Keep workspace_root in sync with the project directory when re-initing.
        if Path(existing.workspace_root).resolve() != root:
            existing = existing.model_copy(update={"workspace_root": str(root)})
            write_council_config(root, existing)
        return existing

    config = CouncilConfig(workspace_root=str(root))
    write_council_config(root, config)
    return config


def clear_workspace_caches() -> None:
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()


def apply_workspace_root(root: Path) -> None:
    """Set process workspace root and invalidate cached settings/guard."""
    resolved = Path(root).expanduser().resolve()
    os.environ["COUNCIL_WORKSPACE_ROOT"] = str(resolved)
    clear_workspace_caches()


def resolve_workspace_root(
    cli_workspace: Path | str | None = None,
    *,
    search_from: Path | str | None = None,
) -> Path:
    """Resolve workspace root: CLI > config.yaml > env > cwd."""
    if cli_workspace is not None:
        return Path(cli_workspace).expanduser().resolve()

    search = Path(search_from) if search_from is not None else Path.cwd()
    search = search.expanduser().resolve()

    if is_sandbox_initialized(search):
        config = load_council_config(search)
        return Path(config.workspace_root).expanduser().resolve()

    env = os.environ.get("COUNCIL_WORKSPACE_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    return search
