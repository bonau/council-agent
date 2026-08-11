"""Shared recursive redaction for durable security evidence."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_VALUE_MAX_CHARS = 2048
REDACTION_MARKER = "[REDACTED]"
TRUNCATION_MARKER = "…[truncated]"

_SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "token",
        "password",
        "passwd",
        "passphrase",
        "secret",
        "clientsecret",
        "privatekey",
        "credential",
        "credentials",
        "cookie",
        "setcookie",
    }
)

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
    r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"
)
_KNOWN_TOKEN_RE = re.compile(
    r"\b(?:"
    r"sk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{12,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[A-Z0-9]{16}"
    r"|AIza[A-Za-z0-9_-]{30,}"
    r")\b"
)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:"
    r"api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|token|"
    r"authorization|password|passwd|passphrase|client[_-]?secret|secret|"
    r"private[_-]?key|credential"
    r")\b\s*(?:=|:)\s*)"
    r"(\[REDACTED\]|\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;&}\]]+)"
)


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_sensitive_key(key: object | None) -> bool:
    if key is None:
        return False
    normalized = _normalized_key(key)
    if normalized in _SENSITIVE_KEYS:
        return True
    return normalized.endswith(
        (
            "apikey",
            "accesstoken",
            "refreshtoken",
            "idtoken",
            "clientsecret",
            "privatekey",
            "password",
            "passphrase",
        )
    )


def redact_text(value: str) -> str:
    """Mask common secret forms embedded in otherwise ordinary text."""

    redacted = _PRIVATE_KEY_RE.sub(REDACTION_MARKER, value)
    redacted = _BEARER_RE.sub(REDACTION_MARKER, redacted)
    redacted = _JWT_RE.sub(REDACTION_MARKER, redacted)
    redacted = _KNOWN_TOKEN_RE.sub(REDACTION_MARKER, redacted)
    return _CREDENTIAL_ASSIGNMENT_RE.sub(
        lambda match: (
            match.group(0)
            if match.group(2) == REDACTION_MARKER
            else f"{match.group(1)}{REDACTION_MARKER}"
        ),
        redacted,
    )


def truncate_text(value: str, *, max_chars: int = DEFAULT_VALUE_MAX_CHARS) -> str:
    """Truncate text with an explicit marker."""

    if len(value) <= max_chars:
        return value
    keep = max(0, max_chars - len(TRUNCATION_MARKER))
    return value[:keep] + TRUNCATION_MARKER


def sanitize_value(
    value: Any,
    *,
    max_chars: int = DEFAULT_VALUE_MAX_CHARS,
    field_name: object | None = None,
) -> Any:
    """Return a JSON-friendly recursively redacted and truncated copy."""

    if _is_sensitive_key(field_name) and value is not None:
        return REDACTION_MARKER
    if isinstance(value, str):
        return truncate_text(redact_text(value), max_chars=max_chars)
    if isinstance(value, dict):
        return {
            str(key): sanitize_value(
                item,
                max_chars=max_chars,
                field_name=key,
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_value(item, max_chars=max_chars) for item in value]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return sanitize_value(str(value), max_chars=max_chars, field_name=field_name)

