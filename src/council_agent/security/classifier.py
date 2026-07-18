"""Command classification for shell tool safety (v0.6)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CommandCategory(str, Enum):
    """Command risk category used by the classifier and run_command gate."""

    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying a shell command string."""

    category: CommandCategory
    matched_rule: str | None = None


# (pattern, rule_id) — evaluated in order; first match wins within a tier.
_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsudo\b", re.IGNORECASE), "sudo"),
    (re.compile(r"\bcurl\b", re.IGNORECASE), "curl"),
    (re.compile(r"\bwget\b", re.IGNORECASE), "wget"),
    (re.compile(r"\bchmod\b", re.IGNORECASE), "chmod"),
    (re.compile(r"\bchown\b", re.IGNORECASE), "chown"),
    # rm with -r and/or -f in short options (e.g. -rf, -fr, -r -f)
    (
        re.compile(
            r"\brm\b(?:\s+-[a-zA-Z]*)*(?:\s+-[a-zA-Z]*[rf][a-zA-Z]*)",
            re.IGNORECASE,
        ),
        "rm-force-or-recursive",
    ),
    (re.compile(r"\bmkfs\b", re.IGNORECASE), "mkfs"),
    (re.compile(r"\bdd\b", re.IGNORECASE), "dd"),
    (re.compile(r"\bshutdown\b", re.IGNORECASE), "shutdown"),
    (re.compile(r"\breboot\b", re.IGNORECASE), "reboot"),
]

_WRITE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmv\b", re.IGNORECASE), "mv"),
    (re.compile(r"\bcp\b", re.IGNORECASE), "cp"),
    (re.compile(r"\btouch\b", re.IGNORECASE), "touch"),
    (re.compile(r"\bmkdir\b", re.IGNORECASE), "mkdir"),
    (re.compile(r"\btee\b", re.IGNORECASE), "tee"),
    (re.compile(r"\brm\b", re.IGNORECASE), "rm"),
    (re.compile(r">\s*\S", re.IGNORECASE), "shell-redirect"),
]


def classify_command(command: str) -> ClassificationResult:
    """Classify a shell command string as read, write, or dangerous.

    Dangerous patterns are checked first, then write patterns. Commands that
    match neither default to ``read``. Matching is case-insensitive regex
    search over the full command string (heuristic, not a full shell parse).
    """
    for pattern, rule_id in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return ClassificationResult(
                category=CommandCategory.DANGEROUS,
                matched_rule=rule_id,
            )

    for pattern, rule_id in _WRITE_PATTERNS:
        if pattern.search(command):
            return ClassificationResult(
                category=CommandCategory.WRITE,
                matched_rule=rule_id,
            )

    return ClassificationResult(category=CommandCategory.READ, matched_rule=None)
