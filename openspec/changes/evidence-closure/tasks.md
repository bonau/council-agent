## 1. Attempt model and deterministic evidence floor

- [ ] 1.1 Add ordered pipeline-attempt, attempt-kind, final stop-reason, and final-result consistency types while preserving existing result accessors.
- [ ] 1.2 Implement pure current-attempt evidence validation for correlation, explicitly required product tools, and required pytest exit/count evidence.
- [ ] 1.3 Add focused unit tests for valid evidence, missing/malformed/failed tests, cross-attempt summaries, and text-only compatibility.
- [ ] 1.4 Run `uv run pytest` and record the all-green phase result before starting boundary wiring.

## 2. Dispatcher and persistence attempt correlation

- [ ] 2.1 Add a context-scoped non-authorizing `pipeline_attempt_id` binding and include it in dispatcher result/tracker metadata.
- [ ] 2.2 Include the same attempt ID in durable audit attempt/result metadata and sandbox session tool records without changing matrix precedence.
- [ ] 2.3 Add direct/Crew/sandbox tests proving result, tracker, session, and audit correlation agree and prior evidence remains append-only.
- [ ] 2.4 Run `uv run pytest` and record the all-green phase result before framework integration.

## 3. Escalation and re-verification integration

- [ ] 3.1 Partition initial execution and escalation summaries by tracker offsets while retaining one cumulative run-level tool limit.
- [ ] 3.2 Mount existing dispatcher-backed Execution Crew tools on escalation.
- [ ] 3.3 Replace the single escalation branch with a bounded retry loop that re-verifies every new execution against the original plan and retains every attempt.
- [ ] 3.4 Make legacy final output/execution/verdict fields and new final attempt/stop reason select the same last attempt.
- [ ] 3.5 Add integration tests for initial PASS, escalation PASS, repeated FAIL/retry exhaustion, zero retries, tool evidence retention, and final-attempt alignment.
- [ ] 3.6 Run `uv run pytest` and record the all-green phase result before documentation work.

## 4. End-to-end evidence and document correction

- [ ] 4.1 Add an end-to-end sandbox orchestration test covering attempt-scoped tracker/session/audit evidence and fail-closed missing test evidence.
- [ ] 4.2 Correct `README.md` and `ROADMAP.md` capability/limitation claims without version bump or Trust Tier runtime claims.
- [ ] 4.3 Close V1-010／SEC-P1-002 and V1-011 documentation debt with accurate residual limitations in known issues and the learning log.
- [ ] 4.4 Correct public testing handbook, manual cases, smoke suite, issue template/index references to the actual v0.9.9 candidate boundary.
- [ ] 4.5 Create `docs/releases/v0.9.9-evidence-closure-evidence.md` and update `docs/releases/v0.9.x-handoff.md` with the explicit v0.9.1–v0.9.9 completion/stop statement, branch, tests, archive plan, and release-branch-only version bump.
- [ ] 4.6 Run `uv run pytest` and record the all-green documentation/e2e phase result.

## 5. Verification, sync, and archive

- [ ] 5.1 Run `uv run pytest`.
- [ ] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [ ] 5.3 Sync the four delta specs into `openspec/specs/` and run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [ ] 5.4 Run `./scripts/check.sh` with the active change and record the test/spec counts in the evidence and learning log.
- [ ] 5.5 Archive `evidence-closure` to the dated archive path and update evidence/handoff with that exact path.
- [ ] 5.6 Run post-archive `./scripts/check.sh`, confirm zero active changes, and record final test/spec counts.
- [ ] 5.7 Commit and push the completed feature branch without changing package version files.
