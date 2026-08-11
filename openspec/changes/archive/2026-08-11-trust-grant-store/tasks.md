## 1. Grant model and user-owned storage boundary

- [x] 1.1 Add strict schema-v1 grant/document/decision models with canonical action, JSON resource, scope, identity, timestamp, expiry, revocation, and unique-ID validation.
- [x] 1.2 Implement default user-data root resolution and fail-closed POSIX ownership, permissions, symlink, ancestor, and workspace-separation validation.
- [x] 1.3 Implement validated inter-process locking, strict locked reads, canonical serialization, same-directory atomic replace, file/directory flush, and validation-only inspection.
- [x] 1.4 Add exact active lookup, expiry, persistent revocation tombstone, duplicate/conflict/corruption/future-schema, restart, and clock-rollback unit tests using only `tmp_path`.
- [x] 1.5 Add concurrent-process, failed-write/replace, unsafe owner/mode/symlink, workspace overlap, and no-partial-adoption tests.
- [x] 1.6 Run the focused grant-store suite and full `uv run pytest` before authentication integration.

## 2. Authenticated management and masked audit

- [x] 2.1 Bind grant/revoke/list to exact one-use `trust-store-management` authentication and enforce `high-risk:manage` or `read` scope before state access/mutation.
- [x] 2.2 Enforce self-grant and current-scope subset rules so principal declaration, project policy, confirmation, `--yes`, or workspace content cannot create or expand authority.
- [x] 2.3 Emit user-owned canonical audit records for authentication, management, and lookup decisions containing only masked principal, creator, grant, action, resource, store, and correlation references.
- [x] 2.4 Add missing/replayed/mismatched/expired/revoked authentication, insufficient-scope, project-policy/workspace bypass, immediate revoke, audit failure, and raw-secret/resource absence tests.
- [x] 2.5 Run the focused authentication/audit grant suite and full `uv run pytest` before CLI wiring.

## 3. Trust CLI foundation

- [x] 3.1 Add `council trust grant` with strict action, JSON resource, repeatable scope, and optional aware expiry inputs.
- [x] 3.2 Add authenticated `council trust revoke` and `council trust list` with non-zero fail-closed diagnostics and no command-line secret input.
- [x] 3.3 Keep trust CLI provider-independent and disconnected from middleware, Trust Tier runtime, `--trust-tier`, confirmation, and `--yes`.
- [x] 3.4 Add CLI tests for success across invocations, missing verifier, scope/auth mismatch, invalid input/store, masked output/audit, revoke/list, project workspace bypass, and unchanged product-tool decisions.
- [x] 3.5 Run CLI-focused tests and full `uv run pytest` before documentation/evidence work.

## 4. Documentation and evidence

- [x] 4.1 Create `docs/releases/v0.9.7-trust-grant-store-evidence.md` with threat model, storage/schema/canonicalization, authentication, atomicity/concurrency, denial/bypass/no-side-effect matrix, redaction, recovery/backup/downgrade guidance, and test counts.
- [x] 4.2 Update `docs/releases/v1.0-alpha-known-issues.md` to close V1-008 only within the v0.9.7 store scope and retain Trust Tier/runtime limitations.
- [x] 4.3 Append the v0.9.7 decisions, evidence, compatibility, residual risks, and next stop to `docs/releases/learning-log-v1-prep.md`.
- [x] 4.4 Update `docs/releases/v0.9.x-handoff.md` with branch, task/test/archive evidence, release-branch-only version bump, and the v0.9.8 stopping point.

## 5. Verification, sync, and archive

- [x] 5.1 Run `uv run pytest` and record the full passing test count.
- [x] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [x] 5.3 Sync the security and orchestration deltas into main specs.
- [x] 5.4 Run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [x] 5.5 Run `./scripts/check.sh` with the active change, archive `trust-grant-store`, then run `./scripts/check.sh` again with no active change.
