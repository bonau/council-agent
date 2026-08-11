"""Session persistence for sandbox tool-call logs."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from council_agent.sandbox.config import (
    is_sandbox_initialized,
    secure_control_directory,
    secure_control_file,
    sessions_dir,
)
from council_agent.security.redaction import sanitize_value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SessionMeta:
    session_id: str
    prompt: str
    preset: str
    workspace_root: str
    started_at: str
    ended_at: str | None = None
    tool_call_count: int = 0
    status: str = "running"


class SessionManager:
    """Create and update `.council/sessions/<id>/` for a single council run."""

    def __init__(self, session_dir: Path, meta: SessionMeta) -> None:
        self.session_dir = Path(session_dir)
        self.meta = meta
        self.meta_path = self.session_dir / "meta.json"
        self.tools_path = self.session_dir / "tools.jsonl"

    @classmethod
    def create(
        cls,
        prompt: str,
        preset: str,
        workspace_root: Path | str,
        *,
        project_root: Path | str | None = None,
    ) -> SessionManager:
        """Create a new session directory with meta.json and empty tools.jsonl."""
        workspace = Path(workspace_root).expanduser().resolve()
        project = (
            Path(project_root).expanduser().resolve()
            if project_root is not None
            else workspace
        )
        if not is_sandbox_initialized(project):
            raise FileNotFoundError(
                f"Sandbox not initialized at {project}; run `council sandbox init` first"
            )

        session_id = str(uuid.uuid4())
        session_dir = sessions_dir(project) / session_id
        session_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        secure_control_directory(session_dir)

        meta = SessionMeta(
            session_id=session_id,
            prompt=str(sanitize_value(prompt)),
            preset=str(sanitize_value(preset)),
            workspace_root=str(workspace),
            started_at=_utc_now_iso(),
        )
        manager = cls(session_dir, meta)
        manager.tools_path.write_text("", encoding="utf-8")
        secure_control_file(manager.tools_path)
        manager._write_meta()
        return manager

    def append_tool_call(
        self,
        tool: str,
        args: dict[str, Any],
        *,
        success: bool,
        metadata: dict[str, Any] | None = None,
        output: str = "",
        error: str | None = None,
        request_id: str | None = None,
        action_id: str | None = None,
        audit_attempt_event_id: str | None = None,
        audit_result_event_id: str | None = None,
    ) -> None:
        """Append one JSON object line to tools.jsonl and bump meta count."""
        record = sanitize_value(
            {
                "tool": tool,
                "args": args,
                "success": success,
                "metadata": metadata or {},
                "output": output,
                "error": error,
                "timestamp": _utc_now_iso(),
                "request_id": request_id,
                "action_id": action_id,
                "audit_attempt_event_id": audit_attempt_event_id,
                "audit_result_event_id": audit_result_event_id,
            }
        )
        with self.tools_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        secure_control_file(self.tools_path)
        self.meta.tool_call_count += 1
        self._write_meta()

    def finalize(self, *, status: str = "completed") -> None:
        """Mark the session finished and persist end timestamp."""
        self.meta.ended_at = _utc_now_iso()
        self.meta.status = status
        self._write_meta()

    def _write_meta(self) -> None:
        self.meta_path.write_text(
            json.dumps(
                sanitize_value(asdict(self.meta)),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        secure_control_file(self.meta_path)

    @classmethod
    def load(cls, session_dir: Path) -> SessionManager:
        meta_path = Path(session_dir) / "meta.json"
        data = sanitize_value(json.loads(meta_path.read_text(encoding="utf-8")))
        meta = SessionMeta(**data)
        return cls(Path(session_dir), meta)

    @classmethod
    def latest(cls, project_root: Path | str) -> SessionManager | None:
        """Return the most recently started session, if any."""
        root = Path(project_root)
        base = sessions_dir(root)
        if not base.is_dir():
            return None

        newest: SessionManager | None = None
        newest_started = ""
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            meta_path = entry / "meta.json"
            if not meta_path.is_file():
                continue
            manager = cls.load(entry)
            if manager.meta.started_at >= newest_started:
                newest_started = manager.meta.started_at
                newest = manager
        return newest

    def count_tool_lines(self) -> int:
        if not self.tools_path.is_file():
            return 0
        text = self.tools_path.read_text(encoding="utf-8")
        return sum(1 for line in text.splitlines() if line.strip())
