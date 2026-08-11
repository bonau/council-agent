## 1. Security Context and Middleware Core

- [x] 1.1 Implement immutable `SecurityContext` creation, validation, one-scope installation/cleanup, and stale-lease rejection in `security/middleware.py`
- [x] 1.2 Extend audit records/loading with backward-compatible phase, request/action correlation, decision, and optional attempt success
- [x] 1.3 Implement the dispatcher core for context validation, registered action lookup, limits, result normalization, tracker/session recording, and attempt/result audit
- [x] 1.4 Add focused unit tests for missing, closed, stale, mismatched, unknown-tool, limit-denied, success, failure, and correlated-audit behavior
- [x] 1.5 Commit and push the core phase, then run `uv run pytest` with the full existing suite green

## 2. Public Tool Boundary

- [x] 2.1 Convert filesystem public functions to dispatcher adapters and private context-requiring guarded operations
- [x] 2.2 Convert shell and pytest public functions to dispatcher adapters while retaining v0.9.1 canonical action, policy, confirmation, containment, and shell-free execution
- [x] 2.3 Ensure top-level tool results/summaries carry one request/action/decision correlation and composite `run_tests` consumes one call
- [x] 2.4 Add bypass-closure, direct-vs-dispatch, no-side-effect, same-action decision, and composite-tool tests
- [x] 2.5 Commit and push the public-boundary phase, then run `uv run pytest` with the full existing suite green

## 3. Orchestrator Wiring

- [x] 3.1 Construct the tracker, optional session/audit objects, loaded policy, confirmation policy, workspace guard, and request identity as one `SecurityContext`
- [x] 3.2 Install one context across planning, execution, verification, and escalation and guarantee cleanup/fail-closed behavior on success and exceptions
- [x] 3.3 Preserve read-only compatibility getters while removing independent policy/confirmation/audit ContextVar installation from the product orchestrator
- [x] 3.4 Add orchestrator tests for one snapshot, sandbox/no-sandbox behavior, cleanup, invalid policy before context, and exception paths
- [x] 3.5 Commit and push the orchestration phase, then run `uv run pytest` with the full existing suite green

## 4. CrewAI Adapter and End-to-End Integration

- [x] 4.1 Reduce `crews/execution_tools.py` to typed CrewAI-to-public-tool adapters and result formatting only
- [x] 4.2 Remove tracker/session binding from adapter construction while keeping middleware-owned summaries available to Verification
- [x] 4.3 Add Crew/direct consistency, no duplicate tracker/session/audit, limit denial, missing-context, and sandboxed end-to-end tests
- [x] 4.4 Commit and push the Crew/e2e phase, then run `uv run pytest` with all existing and new tests green

## 5. Documentation

- [x] 5.1 Update README with the dispatcher-backed library usage, missing-context fail-closed behavior, and explicit no-sandbox evidence behavior
- [x] 5.2 Close SEC-P0-002/V1-003 with evidence references in `docs/releases/v1.0-alpha-known-issues.md`
- [x] 5.3 Append v0.9.2 decisions, entry-point inventory, bypass closure, correlation evidence, and deferred risks to `docs/releases/learning-log-v1-prep.md`
- [x] 5.4 Mark v0.9.2 implementation/handoff state and next v0.9.3 boundary in `docs/releases/v0.9.x-handoff.md`
- [x] 5.5 Commit and push documentation, then run `uv run pytest` with the full suite green

## 6. Verification and Spec Sync

- [x] 6.1 Run `uv run pytest` and record the final test count
- [x] 6.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [x] 6.3 Sync security, tools, and orchestration deltas into `openspec/specs/` and inspect the merged requirements
- [x] 6.4 Run `npx @fission-ai/openspec@latest validate --specs --strict`
- [x] 6.5 Run `./scripts/check.sh`, confirm no version fields changed, and make the final pre-archive commit/push
