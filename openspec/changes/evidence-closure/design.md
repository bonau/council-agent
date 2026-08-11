## Context

See `proposal.md` for motivation. The current orchestrator creates one cumulative `ToolCallTracker`, runs initial Verification once, and replaces `ExecutionResult` after one escalation without replacing the verdict. Execution snapshots the entire tracker, escalation has no tool adapters, and no pipeline-attempt identity is present in result/session/audit metadata. Verification currently delegates PASS/FAIL entirely to model JSON.

The implementation must preserve the one `SecurityContext`, one mandatory dispatcher, cumulative `max_tool_calls`, append-only audit/session evidence, and existing public `CouncilResult` fields. It must not create a second policy or authorization decision.

## Goals / Non-Goals

**Goals:**

- Represent every execution/escalation plus its verification as one immutable, ordered attempt record.
- Make existing final result fields select the final attempt while exposing retained prior attempts and a stable stop reason.
- Partition tracker summaries by attempt and correlate the same ID through dispatcher result, session, and audit metadata.
- Apply deterministic, testable evidence checks after model parsing so required tool/test evidence cannot be waived by model text.
- Keep text-only tasks compatible when no observable tool/test evidence is required.

**Non-Goals:**

- No new Trust Tier, grant lookup, authorization input, policy gate, audit hash chain, or OS containment.
- No new retry configuration; existing `Preset.max_retries` becomes the actual escalation upper bound.
- No package-version or release-tag work.
- No claim that lexical evidence-requirement detection proves arbitrary semantic correctness.

## Decisions

### D1: Ordered `CouncilAttempt` history is the source of final selection

`CouncilAttempt` will contain `attempt_id`, 1-based sequence, kind (`initial` or `escalation`), `ExecutionResult`, and its `VerificationVerdict`. `CouncilResult` keeps backward-compatible `execution`, `verdict`, `final_output`, and `escalated` fields, while adding ordered `attempts`, `final_attempt_id`, and a closed stop reason. Orchestration constructs legacy final fields directly from `attempts[-1]`.

This is preferred over storing only prior verdict strings because complete execution and tool evidence must remain inspectable. The final-attempt consistency is asserted in type validation and tests.

### D2: One cumulative tracker, sliced snapshots per attempt

Execution and escalation record the tracker length before crew kickoff and copy only the new summaries afterward. The tracker itself remains shared in the run `SecurityContext`, so retrying cannot reset or bypass `max_tool_calls`.

This is preferred over one tracker per attempt because the existing limit is explicitly per run and dispatcher/session/audit ownership must remain singular.

### D3: Attempt correlation is execution context, not authority

A small context-scoped pipeline-attempt binding will be installed around each execution plus its Verification. Middleware reads that binding when constructing correlation metadata and audit metadata. No matrix input or policy behavior reads it. Existing request/action/session IDs remain authoritative for action and audit linkage.

This is preferred over replacing `SecurityContext` for every retry because a replacement risks breaking the single-context lifecycle and cumulative tracker/authentication state.

### D4: Escalation uses existing Execution Crew adapters

The escalation Agent receives `build_execution_tools()` and runs within the already installed `SecurityContext`. Its runner captures attempt-scoped summaries exactly like initial execution. The adapter remains a formatter; all decisions and evidence still come from middleware.

### D5: Verification combines model assessment with a deterministic evidence floor

Before returning a model PASS, Verification derives conservative evidence requirements from explicit product-tool names and test/file/command success language in the original request, plan steps, and success criteria. It then checks only current-attempt summaries:

- every summary in an identified pipeline attempt must match that attempt and contain request/action/decision/trust-decision correlation;
- explicitly required product tools must be represented;
- required tests need a latest `run_tests` summary with `success=True`, `exit_code=0`, and `failed=0`.

Evidence failures are appended as issues and force FAIL. A model FAIL remains FAIL. Text-only requests without evidence language do not gain a synthetic requirement.

An alternative was adding planner-generated evidence declarations. That would leave the evidence floor under model control and require a planning schema migration, so deterministic inference is retained for v0.9.9 and documented as conservative lexical matching.

### D6: Retry loop verifies every new output

Initial execution is attempt 1. While its verdict is FAIL and the number of escalations is below `max_retries`, orchestration runs one escalation against the previous execution/verdict and immediately verifies it with the unchanged original plan. It stops on PASS or exhausted retries. Exceptions still fail the session and clean the context.

## Risks / Trade-offs

- [Lexical evidence detection can over- or under-match novel phrasing] → Match explicit tool names and narrow observable-action/test phrases, expose deterministic issues, and document the limitation rather than calling it semantic proof.
- [Adding defaulted result fields can permit legacy callers to create an uncorrelated `CouncilResult`] → Preserve constructor compatibility but make `run_council` always emit complete attempt history; test final-field identity and IDs.
- [Audit attempt metadata and orchestration “attempt” terminology can be confused] → Persist the distinct key `pipeline_attempt_id`; retain `phase=attempt/result` and `attempt_event_id` unchanged.
- [Escalation tools can consume the remaining run budget] → Keep the shared tracker and show tool-limit denial in the escalation attempt evidence.
- [No sandbox means no durable audit] → Continue exposing in-memory request/action/decision/attempt correlation and avoid claiming a durable audit file exists.

## Migration Plan

1. Add types and pure attempt/evidence-correlation helpers with unit tests.
2. Add context-scoped pipeline attempt correlation to middleware/session/audit evidence and verify dispatcher paths.
3. Wire escalation tools, per-attempt summary slicing, retry/re-verification, and final selection.
4. Add deterministic Verification evidence gate and end-to-end orchestration tests for PASS, persistent FAIL, missing evidence, and old-evidence retention.
5. Correct public docs, sync specs, archive, and run the full gate.

Rollback is a normal revert of this feature change; no persistent schema migration is required because `pipeline_attempt_id` is additive metadata and prior audit/session lines remain readable.
