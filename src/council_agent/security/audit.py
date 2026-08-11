"""Structured audit logging for tool invocations (v0.8)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_EVENTS_FILENAME = "events.jsonl"
DEFAULT_ARG_MAX_CHARS = 2048
TRUNCATION_MARKER = "…[truncated]"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truncate_value(value: Any, *, max_chars: int = DEFAULT_ARG_MAX_CHARS) -> Any:
    """Return a JSON-friendly copy with long strings truncated."""
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        keep = max(0, max_chars - len(TRUNCATION_MARKER))
        return value[:keep] + TRUNCATION_MARKER
    if isinstance(value, dict):
        return {str(k): truncate_value(v, max_chars=max_chars) for k, v in value.items()}
    if isinstance(value, list):
        return [truncate_value(v, max_chars=max_chars) for v in value]
    if isinstance(value, tuple):
        return [truncate_value(v, max_chars=max_chars) for v in value]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    # Fallback for non-JSON types
    text = str(value)
    return truncate_value(text, max_chars=max_chars)


@dataclass
class AuditRecord:
    """One structured audit event for a tool invocation."""

    timestamp: str
    tool: str
    args: dict[str, Any]
    success: bool | None
    session_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    phase: str = "result"
    request_id: str | None = None
    action_id: str | None = None
    decision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_audit_events(path: Path | str) -> list[AuditRecord]:
    """Load audit events from a JSONL file; missing file yields empty list."""
    file_path = Path(path)
    if not file_path.is_file():
        return []
    events: list[AuditRecord] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        data = json.loads(text)
        events.append(
            AuditRecord(
                timestamp=data["timestamp"],
                tool=data["tool"],
                args=data.get("args") or {},
                success=data.get("success"),
                session_id=data.get("session_id"),
                error=data.get("error"),
                metadata=data.get("metadata") or {},
                phase=data.get("phase") or "result",
                request_id=data.get("request_id"),
                action_id=data.get("action_id"),
                decision=data.get("decision"),
            )
        )
    return events


class AuditLogger:
    """Append-only JSONL audit logger bound to a project audit directory."""

    def __init__(
        self,
        audit_path: Path | str,
        *,
        session_id: str | None = None,
        arg_max_chars: int = DEFAULT_ARG_MAX_CHARS,
    ) -> None:
        self.audit_path = Path(audit_path)
        self.session_id = session_id
        self.arg_max_chars = arg_max_chars
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.audit_path.exists():
            self.audit_path.write_text("", encoding="utf-8")

    def record(
        self,
        tool: str,
        args: dict[str, Any],
        *,
        success: bool | None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        timestamp: str | None = None,
        phase: str = "result",
        request_id: str | None = None,
        action_id: str | None = None,
        decision: str | None = None,
    ) -> AuditRecord:
        """Append one event and return the stored record."""
        record = AuditRecord(
            timestamp=timestamp or _utc_now_iso(),
            tool=tool,
            args=truncate_value(args, max_chars=self.arg_max_chars),
            success=success,
            session_id=session_id if session_id is not None else self.session_id,
            error=error,
            metadata=truncate_value(metadata or {}, max_chars=self.arg_max_chars),
            phase=phase,
            request_id=request_id,
            action_id=action_id,
            decision=decision,
        )
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return record

    def read_events(self) -> list[AuditRecord]:
        return load_audit_events(self.audit_path)


_LOGGER: ContextVar[AuditLogger | None] = ContextVar(
    "council_audit_logger",
    default=None,
)


def default_audit_events_path(project_root: Path | str) -> Path:
    """Return `.council/audit/events.jsonl` for a project root."""
    from council_agent.sandbox.config import audit_dir

    return audit_dir(Path(project_root)) / DEFAULT_EVENTS_FILENAME


def get_audit_logger() -> AuditLogger | None:
    legacy = _LOGGER.get()
    if legacy is not None:
        return legacy

    from council_agent.security.middleware import get_security_context

    context = get_security_context()
    if context is not None:
        try:
            context.validate(require_active=True)
        except RuntimeError:
            pass
        else:
            return context.audit_logger
    return None


def set_audit_logger(logger: AuditLogger | None) -> Token[AuditLogger | None]:
    return _LOGGER.set(logger)


def reset_audit_logger(token: Token[AuditLogger | None]) -> None:
    _LOGGER.reset(token)


@contextmanager
def audit_logger_context(logger: AuditLogger | None) -> Iterator[AuditLogger | None]:
    """Install an audit logger for the duration of the context."""
    token = set_audit_logger(logger)
    try:
        yield logger
    finally:
        reset_audit_logger(token)


def record_audit_event(
    tool: str,
    args: dict[str, Any],
    *,
    success: bool | None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
    session_id: str | None = None,
    phase: str = "result",
    request_id: str | None = None,
    action_id: str | None = None,
    decision: str | None = None,
) -> AuditRecord | None:
    """Record via the active ContextVar logger, or no-op when unset."""
    logger = get_audit_logger()
    if logger is None:
        return None
    return logger.record(
        tool,
        args,
        success=success,
        error=error,
        metadata=metadata,
        session_id=session_id,
        phase=phase,
        request_id=request_id,
        action_id=action_id,
        decision=decision,
    )


def filter_audit_events(
    events: list[AuditRecord],
    *,
    session_id: str | None = None,
) -> list[AuditRecord]:
    if session_id is None:
        return list(events)
    return [e for e in events if e.session_id == session_id]


def export_audit_events(
    events: list[AuditRecord],
    output_path: Path | str,
    *,
    format: str = "jsonl",
) -> Path:
    """Write events to output_path as JSONL (default) or a JSON array."""
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if format == "json":
        payload = [e.to_dict() for e in events]
        dest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        lines = [json.dumps(e.to_dict(), ensure_ascii=False) for e in events]
        dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return dest
