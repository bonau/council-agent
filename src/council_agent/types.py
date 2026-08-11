"""Shared data types for council agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VerdictStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class AttemptKind(str, Enum):
    INITIAL = "initial"
    ESCALATION = "escalation"


class CouncilStopReason(str, Enum):
    PASSED = "passed"
    RETRIES_EXHAUSTED = "retries_exhausted"
    RETRIES_DISABLED = "retries_disabled"


@dataclass
class PlanArtifact:
    """Structured plan produced by the planning crew."""

    raw: str
    steps: list[str]
    success_criteria: list[str]
    risks: list[str]


@dataclass
class ToolCallSummary:
    """Structured summary of a single tool invocation."""

    tool: str
    success: bool
    output: str
    error: str | None
    metadata: dict

    @classmethod
    def from_result(
        cls,
        name: str,
        args: dict,
        result: "ToolResult",
    ) -> ToolCallSummary:
        from council_agent.tools.base import ToolResult as TR

        if not isinstance(result, TR):
            raise TypeError("result must be a ToolResult")

        return cls(
            tool=name,
            success=result.success,
            output=result.output,
            error=result.error,
            metadata=dict(result.metadata),
        )

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionResult:
    """Output from the execution crew."""

    raw: str
    tool_summaries: list[ToolCallSummary] | None = None
    attempt_id: str | None = None

    def __post_init__(self) -> None:
        if self.tool_summaries is None:
            self.tool_summaries = []
        if self.attempt_id is not None and not self.attempt_id.strip():
            raise ValueError("attempt_id must be non-empty when provided")


@dataclass
class VerificationVerdict:
    """Pass/fail verdict from the verification crew."""

    status: VerdictStatus
    raw: str
    issues: list[str]
    summary: str


@dataclass(frozen=True)
class CouncilAttempt:
    """One execution/escalation and its matching verification verdict."""

    attempt_id: str
    sequence: int
    kind: AttemptKind
    execution: ExecutionResult
    verdict: VerificationVerdict

    def __post_init__(self) -> None:
        if not self.attempt_id.strip():
            raise ValueError("attempt_id must be non-empty")
        if self.sequence < 1:
            raise ValueError("attempt sequence must be positive")
        if self.execution.attempt_id != self.attempt_id:
            raise ValueError("execution attempt_id must match CouncilAttempt")


@dataclass
class CouncilResult:
    """Full result of a council run."""

    prompt: str
    plan: PlanArtifact
    execution: ExecutionResult
    verdict: VerificationVerdict
    escalated: bool
    final_output: str
    attempts: list[CouncilAttempt] = field(default_factory=list)
    final_attempt_id: str | None = None
    stop_reason: CouncilStopReason | None = None

    def __post_init__(self) -> None:
        """Reject internally split final evidence for attempt-aware results."""
        if not self.attempts:
            return

        expected_sequences = list(range(1, len(self.attempts) + 1))
        if [attempt.sequence for attempt in self.attempts] != expected_sequences:
            raise ValueError("attempt sequences must be contiguous and ordered")
        attempt_ids = [attempt.attempt_id for attempt in self.attempts]
        if len(set(attempt_ids)) != len(attempt_ids):
            raise ValueError("attempt IDs must be unique")

        final_attempt = self.attempts[-1]
        if self.final_attempt_id != final_attempt.attempt_id:
            raise ValueError("final_attempt_id must select the last attempt")
        if self.execution is not final_attempt.execution:
            raise ValueError("execution must be the final attempt execution")
        if self.verdict is not final_attempt.verdict:
            raise ValueError("verdict must be the final attempt verdict")
        if self.final_output != final_attempt.execution.raw:
            raise ValueError("final_output must match the final attempt output")
        expected_escalated = any(
            attempt.kind is AttemptKind.ESCALATION for attempt in self.attempts
        )
        if self.escalated is not expected_escalated:
            raise ValueError("escalated must match the retained attempt history")
        if self.stop_reason is None:
            raise ValueError("attempt-aware results require a stop reason")
