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

    def __post_init__(self) -> None:
        if self.tool_summaries is None:
            self.tool_summaries = []


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
