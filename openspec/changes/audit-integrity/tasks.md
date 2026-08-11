## 1. Pure audit integrity primitives

- [x] 1.1 Implement one recursive field/content secret sanitizer that runs before truncation and is safe for nested JSON-compatible and fallback values.
- [x] 1.2 Implement schema-v1 canonical audit records, deterministic event IDs, serialized sequence allocation/append, typed integrity reports/errors, strict structure/digest/correlation validation, and sanitized legacy loading.
- [x] 1.3 Add audit unit tests for redaction, ordinary-value preservation, stable IDs, multiple writers, restart allocation, gaps, duplicates, reorder, malformed/truncated lines, content mutation, dangling/mismatched references, and legacy status; run `uv run pytest tests/test_audit.py`.

## 2. Workspace and session boundaries

- [x] 2.1 Add immutable root/nested built-in denied patterns for audit, sessions, sandbox config, reserved auth/grant paths, and retain project-policy protection across filesystem and recognized shell operands.
- [x] 2.2 Apply owner-only control-plane modes where supported and sanitize session metadata/tool records while retaining request/action/audit event linkage.
- [x] 2.3 Add no-side-effect filesystem/shell sentinel, session redaction/linkage, nested-control-path, policy-non-removal, and permission tests; run `uv run pytest tests/test_workspace_guard.py tests/test_shell_containment.py tests/test_sandbox_session.py`.

## 3. Middleware and CLI integration

- [x] 3.1 Strengthen middleware so every durable result references its exact attempt event and session evidence receives the same request/action and attempt/result IDs.
- [x] 3.2 Make audit show/export report `empty`, `verified`, or `legacy_unverified`, sanitize output, and fail explicitly without exporting invalid history.
- [x] 3.3 Add middleware and CLI integration tests for success/denial correlation, audit-attempt failure, secret-safe persistence/export, integrity status, and invalid-log refusal; run `uv run pytest tests/test_policy_middleware.py tests/test_policy_middleware_tools.py tests/test_cli_audit.py tests/test_sandbox_e2e.py`.

## 4. Evidence and handoff

- [x] 4.1 Create `docs/releases/v0.9.4-audit-integrity-evidence.md` with threat boundary, redaction matrix, sequence/correlation/tamper evidence, migration behavior, test counts, and deferred hash-chain risks.
- [x] 4.2 Update `docs/releases/v1.0-alpha-known-issues.md`, `docs/releases/learning-log-v1-prep.md`, and `docs/releases/v0.9.x-handoff.md` for v0.9.4 closure and v0.9.5 ownership without a version bump.

## 5. Verification and specification sync

- [x] 5.1 Run the complete regression suite with `uv run pytest`.
- [ ] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [ ] 5.3 Sync all four delta specs into `openspec/specs/` and run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [ ] 5.4 Run `./scripts/check.sh` with all active-change tasks complete before archiving.
