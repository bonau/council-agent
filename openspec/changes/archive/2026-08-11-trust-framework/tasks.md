## 1. Pure Trust Tier translator

- [x] 1.1 Add `TrustTier` enum and pure translator mapping tier + risk + grant lookup disposition to closed `GrantState` and confirmation intent without CrewAI or I/O.
- [x] 1.2 Add unit tests for Tier 0/1/2 × risk × grant allowed/not-found/revoked/expired/insufficient vectors and Tier 2 selection preconditions helpers.
- [x] 1.3 Run focused translator tests and full `uv run pytest` before middleware wiring.

## 2. Dispatcher and SecurityContext wiring

- [x] 2.1 Extend `SecurityContext` with `trust_tier` (default 0) and optional `trust_grant_store`; validate Tier 2 cannot be active without step-up configuration when required by product policy.
- [x] 2.2 Replace hard-coded grant disconnect in the mandatory dispatcher with explicit lookup + translator; apply Tier 0 read confirmation; attach `trust_tier` metadata beside matrix evidence.
- [x] 2.3 Add library tests for tier confirmation, grant skip, invalid-grant deny, `--yes`/AUTO non-elevation, no side effects, and store call expectations.
- [x] 2.4 Run dispatcher-focused tests and full `uv run pytest` before CLI/Crew wiring.

## 3. CLI, orchestrator, and Crew integration

- [x] 3.1 Add `council run --trust-tier` (0/1/2, default 0); update help to separate tier, `--yes`, and `council trust` admin.
- [x] 3.2 Orchestrator installs tier on the single product context; Tier 2 performs fresh high-risk step-up before tools; Crew adapters remain formatting-only.
- [x] 3.3 Add CLI/Crew/library parity tests including Tier 2 missing verifier fail-closed and direct/Crew identical matrix evidence.
- [x] 3.4 Run integration-focused tests and full `uv run pytest` before docs/evidence.

## 4. Documentation and evidence

- [x] 4.1 Write `docs/releases/v1.0.0-alpha.1-trust-framework-evidence.md` with translator table, bypass/no-side-effect vectors, and test counts.
- [x] 4.2 Update README, ROADMAP status, known-issues, handoff, testing manuals/smoke for Trust Tier runtime boundaries and Non-goals.
- [x] 4.3 Append learning-log entry for trust-framework implementation.

## 5. Verification, sync, and archive

- [x] 5.1 Run `uv run pytest` and record the full passing count.
- [x] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [x] 5.3 Sync security, tools, orchestration, and release-prep deltas into main specs.
- [x] 5.4 Run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [x] 5.5 Run `./scripts/check.sh` with the active change, archive `trust-framework`, then run `./scripts/check.sh` with no active change.
