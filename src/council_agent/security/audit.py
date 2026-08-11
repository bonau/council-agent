"""Structured audit logging for tool invocations (v0.8)."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from council_agent.security.redaction import (
    DEFAULT_VALUE_MAX_CHARS,
    REDACTION_MARKER,
    TRUNCATION_MARKER,
    sanitize_value,
    truncate_text,
)

DEFAULT_EVENTS_FILENAME = "events.jsonl"
DEFAULT_ARG_MAX_CHARS = DEFAULT_VALUE_MAX_CHARS
AUDIT_SCHEMA_VERSION = 1
AUDIT_EVENT_ID_PREFIX = "sha256:"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truncate_value(value: Any, *, max_chars: int = DEFAULT_ARG_MAX_CHARS) -> Any:
    """Return a JSON-friendly copy with long strings truncated."""
    if isinstance(value, str):
        return truncate_text(value, max_chars=max_chars)
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
    schema_version: int = AUDIT_SCHEMA_VERSION
    sequence: int | None = None
    event_id: str | None = None
    attempt_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditIntegrityError(ValueError):
    """Raised when an audit file cannot be treated as valid history."""

    def __init__(self, reason: str, *, line_number: int | None = None) -> None:
        location = f" at line {line_number}" if line_number is not None else ""
        super().__init__(f"Audit integrity validation failed{location}: {reason}")
        self.reason = reason
        self.line_number = line_number


@dataclass(frozen=True)
class AuditIntegrityReport:
    """Integrity state for one successfully parsed audit history."""

    status: str
    total_events: int
    verified_events: int
    legacy_events: int
    last_sequence: int


_AUDIT_FIELDS = frozenset(AuditRecord.__dataclass_fields__)
_PATH_LOCKS: dict[Path, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def canonical_audit_json(record: AuditRecord) -> str:
    """Return the canonical JSON covered by a schema-v1 event identity."""

    payload = record.to_dict()
    payload.pop("event_id", None)
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def compute_audit_event_id(record: AuditRecord) -> str:
    """Derive a deterministic event identity from its stored envelope."""

    digest = hashlib.sha256(canonical_audit_json(record).encode("utf-8")).hexdigest()
    return f"{AUDIT_EVENT_ID_PREFIX}{digest}"


def _integrity_error(reason: str, index: int | None = None) -> AuditIntegrityError:
    return AuditIntegrityError(
        reason,
        line_number=None if index is None else index + 1,
    )


def _record_from_data(data: object, *, index: int) -> AuditRecord:
    if not isinstance(data, dict):
        raise _integrity_error("record must be a JSON object", index)

    version = data.get("schema_version", 0)
    if isinstance(version, bool) or not isinstance(version, int):
        raise _integrity_error("schema_version must be an integer", index)
    if version not in {0, AUDIT_SCHEMA_VERSION}:
        raise _integrity_error("unsupported schema_version", index)
    if version == AUDIT_SCHEMA_VERSION:
        unknown = sorted(set(data) - _AUDIT_FIELDS)
        if unknown:
            raise _integrity_error("versioned record contains unknown fields", index)

    timestamp = data.get("timestamp")
    tool = data.get("tool")
    args = data.get("args", {})
    metadata = data.get("metadata", {})
    success = data.get("success")
    if not isinstance(timestamp, str) or not timestamp:
        raise _integrity_error("timestamp must be a non-empty string", index)
    if not isinstance(tool, str) or not tool:
        raise _integrity_error("tool must be a non-empty string", index)
    if not isinstance(args, dict):
        raise _integrity_error("args must be an object", index)
    if not isinstance(metadata, dict):
        raise _integrity_error("metadata must be an object", index)
    if success is not None and not isinstance(success, bool):
        raise _integrity_error("success must be boolean or null", index)

    return AuditRecord(
        timestamp=timestamp,
        tool=tool,
        args=args,
        success=success,
        session_id=data.get("session_id"),
        error=data.get("error"),
        metadata=metadata,
        phase=data.get("phase") or "result",
        request_id=data.get("request_id"),
        action_id=data.get("action_id"),
        decision=data.get("decision"),
        schema_version=version,
        sequence=data.get("sequence"),
        event_id=data.get("event_id"),
        attempt_event_id=data.get("attempt_event_id"),
    )


def _parse_audit_events(path: Path) -> list[AuditRecord]:
    if not path.is_file():
        return []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditIntegrityError("audit file could not be read") from exc
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise AuditIntegrityError("audit file has an unterminated final record")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditIntegrityError("audit file is not valid UTF-8") from exc

    events: list[AuditRecord] = []
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            raise _integrity_error("blank record line", index)
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise _integrity_error("record is not valid JSON", index) from exc
        events.append(_record_from_data(data, index=index))
    return events


def verify_audit_events(
    events: list[AuditRecord],
    *,
    require_complete: bool = True,
) -> AuditIntegrityReport:
    """Validate versioned envelopes, ordering, and attempt/result references."""

    expected_sequence = 1
    legacy_events = 0
    verified_events = 0
    saw_versioned = False
    seen_ids: set[str] = set()
    pending_attempts: dict[str, AuditRecord] = {}

    for index, event in enumerate(events):
        if event.schema_version == 0:
            if saw_versioned:
                raise _integrity_error(
                    "legacy record appears after versioned history",
                    index,
                )
            legacy_events += 1
            continue
        if event.schema_version != AUDIT_SCHEMA_VERSION:
            raise _integrity_error("unsupported schema_version", index)
        saw_versioned = True
        if (
            isinstance(event.sequence, bool)
            or not isinstance(event.sequence, int)
            or event.sequence <= 0
        ):
            raise _integrity_error("sequence must be a positive integer", index)
        if event.sequence != expected_sequence:
            raise _integrity_error(
                f"expected sequence {expected_sequence}, got {event.sequence}",
                index,
            )
        expected_sequence += 1
        if not isinstance(event.event_id, str) or not event.event_id:
            raise _integrity_error("event_id must be a non-empty string", index)
        if event.event_id in seen_ids:
            raise _integrity_error("duplicate event_id", index)
        if event.event_id != compute_audit_event_id(event):
            raise _integrity_error("event_id does not match canonical content", index)
        seen_ids.add(event.event_id)
        verified_events += 1

        if event.phase == "attempt":
            if not event.request_id or not event.action_id:
                raise _integrity_error(
                    "attempt requires request_id and action_id",
                    index,
                )
            if event.attempt_event_id is not None:
                raise _integrity_error(
                    "attempt cannot reference another attempt",
                    index,
                )
            pending_attempts[event.event_id] = event
        elif event.phase == "result":
            if event.action_id is None:
                if event.attempt_event_id is not None:
                    raise _integrity_error(
                        "administrative result cannot reference an attempt",
                        index,
                    )
                continue
            if not event.attempt_event_id:
                raise _integrity_error("result is missing attempt_event_id", index)
            attempt = pending_attempts.pop(event.attempt_event_id, None)
            if attempt is None:
                raise _integrity_error(
                    "result references a missing or completed attempt",
                    index,
                )
            if (
                attempt.request_id,
                attempt.action_id,
                attempt.session_id,
                attempt.tool,
            ) != (
                event.request_id,
                event.action_id,
                event.session_id,
                event.tool,
            ):
                raise _integrity_error(
                    "result correlation does not match its attempt",
                    index,
                )
        else:
            raise _integrity_error("phase must be attempt or result", index)

    if require_complete and pending_attempts:
        raise AuditIntegrityError(
            f"{len(pending_attempts)} attempt event(s) have no result"
        )
    status = (
        "empty"
        if not events
        else "legacy_unverified"
        if legacy_events
        else "verified"
    )
    return AuditIntegrityReport(
        status=status,
        total_events=len(events),
        verified_events=verified_events,
        legacy_events=legacy_events,
        last_sequence=expected_sequence - 1,
    )


def load_audit_events_with_integrity(
    path: Path | str,
    *,
    require_complete: bool = True,
) -> tuple[list[AuditRecord], AuditIntegrityReport]:
    """Load, validate, and sanitize an audit JSONL file."""

    events = _parse_audit_events(Path(path))
    report = verify_audit_events(events, require_complete=require_complete)
    sanitized = [
        replace(
            event,
            args=sanitize_value(event.args),
            error=sanitize_value(event.error),
            metadata=sanitize_value(event.metadata),
        )
        for event in events
    ]
    return sanitized, report


def load_audit_events(path: Path | str) -> list[AuditRecord]:
    """Load validated, sanitized audit events; missing file yields an empty list."""

    events, _report = load_audit_events_with_integrity(path)
    return events


@contextmanager
def _audit_path_lock(path: Path) -> Iterator[None]:
    resolved = path.resolve()
    with _PATH_LOCKS_GUARD:
        local_lock = _PATH_LOCKS.setdefault(resolved, threading.RLock())
    with local_lock:
        lock_path = resolved.with_name(f"{resolved.name}.lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                import fcntl
            except ImportError:  # pragma: no cover - non-POSIX fallback
                fcntl = None  # type: ignore[assignment]
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _append_record(path: Path, record: AuditRecord) -> None:
    encoded = (
        json.dumps(
            record.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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
        self.audit_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.audit_path.parent, 0o700)
        descriptor = os.open(
            self.audit_path,
            os.O_CREAT | os.O_APPEND | os.O_WRONLY,
            0o600,
        )
        os.close(descriptor)
        os.chmod(self.audit_path, 0o600)

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
        attempt_event_id: str | None = None,
    ) -> AuditRecord:
        """Append one event and return the stored record."""
        with _audit_path_lock(self.audit_path):
            existing = _parse_audit_events(self.audit_path)
            report = verify_audit_events(existing, require_complete=False)
            record = AuditRecord(
                timestamp=timestamp or _utc_now_iso(),
                tool=str(sanitize_value(tool, max_chars=self.arg_max_chars)),
                args=sanitize_value(args, max_chars=self.arg_max_chars),
                success=success,
                session_id=session_id if session_id is not None else self.session_id,
                error=sanitize_value(error, max_chars=self.arg_max_chars),
                metadata=sanitize_value(
                    metadata or {},
                    max_chars=self.arg_max_chars,
                ),
                phase=phase,
                request_id=request_id,
                action_id=action_id,
                decision=decision,
                schema_version=AUDIT_SCHEMA_VERSION,
                sequence=report.last_sequence + 1,
                attempt_event_id=attempt_event_id,
            )
            record = replace(record, event_id=compute_audit_event_id(record))
            verify_audit_events([*existing, record], require_complete=False)
            _append_record(self.audit_path, record)
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
    attempt_event_id: str | None = None,
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
        attempt_event_id=attempt_event_id,
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
        payload = [sanitize_value(e.to_dict()) for e in events]
        dest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        lines = [
            json.dumps(sanitize_value(e.to_dict()), ensure_ascii=False)
            for e in events
        ]
        dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return dest
