"""Deterministic Verification evidence and attempt-model tests."""

from __future__ import annotations

import pytest

from council_agent.crews.verification import validate_required_evidence
from council_agent.types import (
    AttemptKind,
    CouncilAttempt,
    CouncilResult,
    CouncilStopReason,
    ExecutionResult,
    PlanArtifact,
    ToolCallSummary,
    VerdictStatus,
    VerificationVerdict,
)


def _plan(*, steps: list[str], criteria: list[str]) -> PlanArtifact:
    return PlanArtifact(
        raw="{}",
        steps=steps,
        success_criteria=criteria,
        risks=[],
    )


def _verdict(status: VerdictStatus = VerdictStatus.PASS) -> VerificationVerdict:
    return VerificationVerdict(
        status=status,
        raw=f'{{"status":"{status.value}"}}',
        issues=[],
        summary=status.value.lower(),
    )


def _summary(
    tool: str,
    *,
    attempt_id: str = "attempt-1",
    success: bool = True,
    metadata: dict | None = None,
) -> ToolCallSummary:
    correlation = {
        "pipeline_attempt_id": attempt_id,
        "request_id": "request-1",
        "action_id": f"action-{tool}",
        "decision": "allow",
        "trust_decision": {
            "version": 1,
            "outcome": "allow",
            "reason": "decision_allowed",
        },
    }
    correlation.update(metadata or {})
    return ToolCallSummary(
        tool=tool,
        success=success,
        output="ok",
        error=None if success else "failed",
        metadata=correlation,
    )


def test_attempt_aware_result_selects_one_final_attempt() -> None:
    execution = ExecutionResult(raw="done", attempt_id="attempt-1")
    verdict = _verdict()
    attempt = CouncilAttempt(
        attempt_id="attempt-1",
        sequence=1,
        kind=AttemptKind.INITIAL,
        execution=execution,
        verdict=verdict,
    )

    result = CouncilResult(
        prompt="text answer",
        plan=_plan(steps=["answer"], criteria=["complete answer"]),
        execution=execution,
        verdict=verdict,
        escalated=False,
        final_output="done",
        attempts=[attempt],
        final_attempt_id="attempt-1",
        stop_reason=CouncilStopReason.PASSED,
    )

    assert result.attempts[-1].execution is result.execution
    assert result.attempts[-1].verdict is result.verdict


def test_attempt_aware_result_rejects_split_final_evidence() -> None:
    initial = ExecutionResult(raw="old", attempt_id="attempt-1")
    final = ExecutionResult(raw="new", attempt_id="attempt-2")
    old_verdict = _verdict(VerdictStatus.FAIL)
    final_verdict = _verdict()
    attempts = [
        CouncilAttempt(
            "attempt-1",
            1,
            AttemptKind.INITIAL,
            initial,
            old_verdict,
        ),
        CouncilAttempt(
            "attempt-2",
            2,
            AttemptKind.ESCALATION,
            final,
            final_verdict,
        ),
    ]

    with pytest.raises(ValueError, match="execution must be the final"):
        CouncilResult(
            prompt="fix",
            plan=_plan(steps=["fix"], criteria=["fixed"]),
            execution=initial,
            verdict=final_verdict,
            escalated=True,
            final_output="new",
            attempts=attempts,
            final_attempt_id="attempt-2",
            stop_reason=CouncilStopReason.PASSED,
        )


def test_required_passing_test_evidence_is_accepted() -> None:
    plan = _plan(steps=["run pytest"], criteria=["all tests pass"])
    execution = ExecutionResult(
        raw="done",
        attempt_id="attempt-1",
        tool_summaries=[
            _summary(
                "run_tests",
                metadata={"exit_code": 0, "passed": 8, "failed": 0, "skipped": 1},
            )
        ],
    )

    assert validate_required_evidence("fix it", plan, execution) == []


@pytest.mark.parametrize(
    ("summaries", "expected"),
    [
        ([], "Required tool evidence is missing: run_tests"),
        (
            [_summary("run_tests", metadata={"passed": 1})],
            "Required test evidence is incomplete",
        ),
        (
            [
                _summary(
                    "run_tests",
                    success=False,
                    metadata={"exit_code": 1, "failed": 1},
                )
            ],
            "Required test evidence did not pass",
        ),
    ],
)
def test_required_test_evidence_fails_closed(
    summaries: list[ToolCallSummary],
    expected: str,
) -> None:
    plan = _plan(steps=["run tests"], criteria=["tests pass"])
    execution = ExecutionResult(
        raw="claimed success",
        attempt_id="attempt-1",
        tool_summaries=summaries,
    )

    assert any(
        expected in issue
        for issue in validate_required_evidence("fix it", plan, execution)
    )


def test_cross_attempt_tool_evidence_is_rejected() -> None:
    execution = ExecutionResult(
        raw="claimed success",
        attempt_id="attempt-2",
        tool_summaries=[_summary("write_file", attempt_id="attempt-1")],
    )

    issues = validate_required_evidence(
        "Use write_file to update the file",
        _plan(steps=["update"], criteria=["file updated"]),
        execution,
    )

    assert "Tool evidence does not belong to the current pipeline attempt" in issues


def test_current_attempt_tool_evidence_requires_decision_correlation() -> None:
    summary = _summary("write_file")
    summary.metadata.pop("trust_decision")
    execution = ExecutionResult(
        raw="claimed success",
        attempt_id="attempt-1",
        tool_summaries=[summary],
    )

    issues = validate_required_evidence(
        "Use write_file",
        _plan(steps=["write file"], criteria=["file updated"]),
        execution,
    )

    assert any("trust_decision" in issue for issue in issues)


def test_text_only_plan_does_not_invent_tool_requirement() -> None:
    execution = ExecutionResult(raw="a concise answer", attempt_id="attempt-1")

    assert (
        validate_required_evidence(
            "Explain the architecture",
            _plan(
                steps=["summarize the architecture"],
                criteria=["clear and accurate explanation"],
            ),
            execution,
        )
        == []
    )
