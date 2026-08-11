## 1. Pure decision contract

- [x] 1.1 Add closed schema-v1 policy, scope, authentication, grant, action-risk, interaction, outcome, and stable-reason models without CrewAI or runtime I/O.
- [x] 1.2 Implement deterministic precedence evaluation and JSON-safe normalized evidence for `deny`, `require_confirmation`, and `allow`.
- [x] 1.3 Add exhaustive table/property-style tests for every state, simultaneous-denial precedence, reason stability, serialization, and absence of raw authority data.
- [x] 1.4 Run the focused decision-matrix tests and full `uv run pytest` before dispatcher wiring.

## 2. Dispatcher and library integration

- [x] 2.1 Normalize existing policy, scope, authentication, action-risk, and confirmation results at the mandatory dispatcher; set v0.9.8 product grant state explicitly to not required.
- [x] 2.2 Attach one namespaced matrix version/vector/outcome/reason to result, tracker, session, and audit evidence without replacing detailed legacy evidence.
- [x] 2.3 Add library tests for policy/scope/authentication/grant-contract/risk/interaction precedence, `AUTO` bypass resistance, stable reasons, ordinary operation failures, audit consistency, and no side effects.
- [x] 2.4 Run dispatcher-focused tests and full `uv run pytest` before framework/CLI integration.

## 3. Crew and CLI integration

- [x] 3.1 Keep Crew adapters formatting-only and verify direct library and Crew actions under equivalent contexts produce identical dispatcher matrix evidence.
- [x] 3.2 Update `council run --yes` help to state that it skips prompts only and cannot create scopes, authentication, grants, or privilege.
- [x] 3.3 Add CLI-resolved context and end-to-end tests proving `--yes`/`AUTO` cannot override scope, authentication, policy, or invalid-grant matrix states and that no `--trust-tier` option exists.
- [x] 3.4 Run Crew/CLI-focused tests and full `uv run pytest` before documentation/evidence work.

## 4. Documentation and evidence

- [x] 4.1 Create `docs/releases/v0.9.8-trust-decision-matrix-evidence.md` with matrix version, complete table, stable reasons, denial/bypass/no-side-effect vectors, entry-point equivalence, compatibility, test counts, and deferred tier wiring.
- [x] 4.2 Update `docs/releases/v1.0-alpha-known-issues.md` to close V1-009/SEC-P0-005 only for the matrix/interaction separation while retaining the Trust Tier runtime stop.
- [x] 4.3 Append approved v0.9.8 inputs, precedence, reason codes, `ConfirmMode` migration/compatibility, `--yes`/non-TTY/auth/grant vectors, residual risks, and v1.0-alpha wiring list to `docs/releases/learning-log-v1-prep.md`.
- [x] 4.4 Update `docs/releases/v0.9.x-handoff.md` with branch, task/test/archive evidence, release-branch-only version bump, and the v0.9.9 handoff.

## 5. Verification, sync, and archive

- [ ] 5.1 Run `uv run pytest` and record the full passing test count.
- [ ] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [ ] 5.3 Sync the security, tools, and orchestration deltas into main specs.
- [ ] 5.4 Run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [ ] 5.5 Run `./scripts/check.sh` with the active change, archive `trust-decision-matrix`, then run `./scripts/check.sh` again with no active change.
