## 1. Authentication primitives and lifecycle

- [x] 1.1 Add immutable authentication binding, challenge, opaque token, decision, and stable reason models.
- [x] 1.2 Implement process-local challenge issue/completion, exact binding, expiry/freshness, one-use replay tombstones, and manager revocation.
- [x] 1.3 Implement typed non-interactive service verifier response/provider without persisting or displaying credential material.
- [x] 1.4 Add unit tests for success, wrong credential/binding, challenge and token replay, expiry/freshness, revoke, restart invalidation, and masked lifecycle events.
- [x] 1.5 Run `uv run pytest` with the authentication primitive suite included before middleware integration.

## 2. Dispatcher and security-context integration

- [x] 2.1 Extend the immutable security context with independent authentication manager/provider state and a non-empty runtime session binding.
- [x] 2.2 Require fresh exact-action step-up after scope authorization for actions requiring `high-risk:manage`, before confirmation/handler execution.
- [x] 2.3 Add normalized masked authentication metadata to correlated attempt/result and session evidence.
- [x] 2.4 Add direct/Crew high-risk tests for missing, expired, revoked, replayed, wrong principal/workspace/session/action proofs and no process/filesystem side effects.
- [x] 2.5 Prove ordinary actions remain compatible and authenticated high-risk actions still obey project policy and confirmation.
- [x] 2.6 Run `uv run pytest` with dispatcher integration included before orchestration wiring.

## 3. Orchestrator and CLI wiring

- [x] 3.1 Add a dedicated optional `SecretStr` authentication verifier setting and documented environment input separate from provider/principal configuration.
- [x] 3.2 Construct run-local authentication state and audit sink in the orchestrator, bind sandbox and non-sandbox runtime sessions, and revoke on every exit path.
- [x] 3.3 Pass verifier state from CLI without adding a command-line secret or displaying credential/proof values.
- [x] 3.4 Add CLI/orchestrator tests proving `--yes` alone cannot satisfy step-up, configured service authentication can, and cleanup/restart fail closed.
- [x] 3.5 Run `uv run pytest` with orchestration/CLI integration included before end-to-end verification.

## 4. End-to-end security evidence

- [x] 4.1 Add sandboxed end-to-end coverage for authenticated high-risk success and `--yes`-only denial using `tmp_path`.
- [x] 4.2 Assert success/failure/expiry/revoke/replay lifecycle events are masked and raw verifier/challenge/response/token values are absent from audit, session, and captured console output.
- [x] 4.3 Run the full `uv run pytest` regression and record the passing test count.

## 5. Documentation and final verification

- [x] 5.1 Create `docs/releases/v0.9.6-session-auth-evidence.md` with threat model, bindings, denial/no-side-effect matrix, redaction evidence, test counts, and remaining limits.
- [x] 5.2 Update v1.0 known issues, learning log, and v0.9.x handoff for V1-007 without version bump or Trust Tier/grant claims.
- [x] 5.3 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [x] 5.4 Sync the security, sandbox, and orchestration deltas into main specs.
- [x] 5.5 Run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [x] 5.6 Run `./scripts/check.sh` before archive, archive `session-auth`, then run `./scripts/check.sh` again with no active change.
