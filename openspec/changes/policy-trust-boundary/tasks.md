## 1. Strict project-policy schema and restrict-only model

- [x] 1.1 Add required integer schema version 1, strict known-field validation, sanitized diagnostics, and explicit unversioned/unsupported migration refusal in the pure policy loader.
- [x] 1.2 Add policy unit tests for valid version 1, missing/unsupported/wrong-typed versions, unknown fields, misspellings, invalid known fields, secret-value omission, and whole-file refusal.
- [x] 1.3 Add restrict-only unit tests proving allow patterns cannot bypass built-in command rejection, confirmation, command deny precedence, or default path denials.
- [x] 1.4 Run `uv run pytest` with the full existing suite before middleware/orchestrator wiring.

## 2. SecurityContext and orchestrator wiring

- [ ] 2.1 Derive and validate `SecurityContext.policy_version` as `builtin` or `project-policy/v1` from the captured policy snapshot.
- [ ] 2.2 Update orchestrator tests and fixtures to use version 1 policy, prove schema/version/unknown-field failures occur before session/context/crews, and assert one versioned snapshot through the pipeline.
- [ ] 2.3 Run `uv run pytest` with the full suite before adding framework/tool boundary protection.

## 3. Product tool policy-file protection

- [ ] 3.1 Add root and nested `council.policy.yaml` patterns to the immutable built-in `WorkspaceGuard` denylist.
- [ ] 3.2 Add `tmp_path` tests proving root/nested guard denial, policy inability to remove protection, and public filesystem/supported shell mutation refusal with unchanged policy-file sentinel.
- [ ] 3.3 Run `uv run pytest` with the full suite before documentation and end-to-end evidence.

## 4. Documentation and compatibility evidence

- [ ] 4.1 Update README with schema version 1, migration steps, restrict-only semantics, policy-file tool protection, user-owned trust-store separation, and the `run_tests`/OS-containment limitation.
- [ ] 4.2 Update known issues, v1-prep learning log, v0.9.x handoff, and add `docs/releases/v0.9.3-policy-trust-boundary-evidence.md` with rejection, no-side-effect, compatibility, and deferred-scope evidence.
- [ ] 4.3 Run `uv run pytest` with the full suite after documentation/evidence integration.

## 5. Verification, spec sync, and archive readiness

- [ ] 5.1 Run `uv run pytest` and record the final passing test count.
- [ ] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [ ] 5.3 Sync all security/sandbox/orchestration deltas to main specs and run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [ ] 5.4 Run `./scripts/check.sh` on the complete active change before archive and record the result; after all tasks are complete, archive the change and repeat the post-archive gate.
