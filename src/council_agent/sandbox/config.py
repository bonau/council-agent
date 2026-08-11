"""`.council/config.yaml` schema, loader, and workspace resolution."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from council_agent.config.settings import get_settings
from council_agent.sandbox.workspace import get_workspace_guard

CONTROL_DIRECTORY_MODE = 0o700
CONTROL_FILE_MODE = 0o600


def secure_control_directory(path: Path) -> Path:
    """Create a control-plane directory and request owner-only access."""

    target = Path(path)
    target.mkdir(parents=True, exist_ok=True, mode=CONTROL_DIRECTORY_MODE)
    try:
        target.chmod(CONTROL_DIRECTORY_MODE)
    except OSError:
        pass
    return target


def secure_control_file(path: Path) -> Path:
    """Request owner-only access for an existing control-plane file."""

    target = Path(path)
    try:
        target.chmod(CONTROL_FILE_MODE)
    except OSError:
        pass
    return target


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


def audit_dir(project_root: Path) -> Path:
    return council_dir(project_root) / "audit"


def is_sandbox_initialized(project_root: Path) -> bool:
    return config_path(project_root).is_file()


def load_council_config(project_root: Path) -> CouncilConfig:
    path = config_path(project_root)
    if not path.is_file():
        raise FileNotFoundError(f"Sandbox config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CouncilConfig.model_validate(data)


def write_council_config(project_root: Path, config: CouncilConfig) -> None:
    council = secure_control_directory(council_dir(project_root))
    secure_control_directory(sessions_dir(project_root))
    secure_control_directory(audit_dir(project_root))
    payload = config.model_dump()
    config_path(project_root).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    secure_control_file(config_path(project_root))


def init_sandbox(project_root: Path) -> CouncilConfig:
    """Create `.council/` idempotently; never delete existing sessions or audit."""
    root = Path(project_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    secure_control_directory(council_dir(root))
    secure_control_directory(sessions_dir(root))
    secure_control_directory(audit_dir(root))

    path = config_path(root)
    if path.is_file():
        secure_control_file(path)
        existing = load_council_config(root)
        # Keep workspace_root in sync with the project directory when re-initing.
        if Path(existing.workspace_root).resolve() != root:
            existing = existing.model_copy(update={"workspace_root": str(root)})
            write_council_config(root, existing)
        else:
            # Ensure audit/ exists even for older sandboxes without rewriting config.
            secure_control_directory(audit_dir(root))
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
