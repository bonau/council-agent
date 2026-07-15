"""Shared data types for council agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VerdictStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class PlanArtifact:
    """Structured plan produced by the planning crew."""

    raw: str
    steps: list[str]
    success_criteria: list[str]
    risks: list[str]


@dataclass
class ExecutionResult:
    """Output from the execution crew."""

    raw: str


@dataclass
class VerificationVerdict:
    """Pass/fail verdict from the verification crew."""

    status: VerdictStatus
    raw: str
    issues: list[str]
    summary: str


@dataclass
class CouncilResult:
    """Full result of a council run."""

    prompt: str
    plan: PlanArtifact
    execution: ExecutionResult
    verdict: VerificationVerdict
    escalated: bool
    final_output: str
