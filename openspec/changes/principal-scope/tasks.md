## 1. Principal and credential core

- [x] 1.1 Add immutable, strictly validated Council principal/kind/scope types, stable masked references, and strict scope parsing.
- [x] 1.2 Add a non-revealing typed OpenRouter provider credential that cannot be used as a Council principal.
- [x] 1.3 Add the pure cumulative tool/action scope matrix and stable allow/deny decision reasons, including shell category requirements.
- [x] 1.4 Add focused unit tests for valid/invalid principals, unknown scopes, masked identity stability, provider/principal type separation, and every scope-matrix row.
- [x] 1.5 Run `uv run pytest` and keep the full existing suite green before dispatcher integration.

## 2. Dispatcher authorization and evidence

- [x] 2.1 Extend `SecurityContext` with an expected principal binding and optional current-authority resolver without adding authentication or grant semantics.
- [x] 2.2 Enforce current principal and cumulative scope requirements in the mandatory dispatcher before handlers, policy, confirmation, filesystem access, or subprocess creation.
- [x] 2.3 Add masked authorization metadata to correlated attempt/result and session evidence while preserving audit schema-v1 compatibility.
- [x] 2.4 Add middleware tests for missing/invalid/mismatched/insufficient principals, scope tightening, immediate revocation, confirmation/policy non-elevation, masked audit linkage, and no side effects.
- [x] 2.5 Run `uv run pytest` and keep the full suite green before orchestration/framework wiring.

## 3. Orchestration and provider boundary

- [x] 3.1 Replace raw provider-key parameters across OpenRouter and crew builders with the typed provider credential.
- [x] 3.2 Require `run_council` to receive a separate Council principal/current-authority source and install only principal data in `SecurityContext`.
- [x] 3.3 Add strict Council-specific CLI principal identity/scope settings with a full-scope local compatibility default and update `.env.example`/README configuration guidance.
- [x] 3.4 Add orchestration and CLI tests proving provider credentials do not authorize tools, principal data does not reach model credentials, unknown scopes fail before crews, and cleanup removes authority.
- [x] 3.5 Run `uv run pytest` and keep the full suite green before wrapper/end-to-end coverage.

## 4. Wrapper, composite, and end-to-end bypass coverage

- [x] 4.1 Add direct and CrewAI-wrapper matrix tests showing equivalent scope decisions and no second executable path.
- [x] 4.2 Add read-only and partial-scope `run_tests` tests proving no pytest process or mutation sentinel side effect and one top-level decision.
- [x] 4.3 Add shell read/write/dangerous scope-combination tests proving denial precedes process creation, project policy, and confirmation.
- [ ] 4.4 Run `uv run pytest` with all unit, integration, security, and end-to-end tests green.

## 5. Documentation and release evidence

- [ ] 5.1 Create `docs/releases/v0.9.5-principal-scope-evidence.md` with scope matrix, provider/principal flow, positive/refusal/bypass/no-side-effect/audit evidence, test counts, and limitations.
- [ ] 5.2 Close V1-006 in `docs/releases/v1.0-alpha-known-issues.md` while retaining v0.9.6 authentication, v0.9.7 grants, and Trust Tier as open boundaries.
- [ ] 5.3 Append v0.9.5 decisions/results to `docs/releases/learning-log-v1-prep.md` and update `docs/releases/v0.9.x-handoff.md` status/next-version guidance.

## 6. Verification, synchronization, and archive

- [ ] 6.1 Run `uv run pytest`.
- [ ] 6.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`.
- [ ] 6.3 Sync all `principal-scope` deltas into `openspec/specs/` and run `npx @fission-ai/openspec@latest validate --specs --strict`.
- [ ] 6.4 Run `./scripts/check.sh` with the active change and record the exact passing test/spec counts in evidence.
- [ ] 6.5 Archive `principal-scope`, verify there are no active changes, and run post-archive `./scripts/check.sh`.
- [ ] 6.6 Confirm no version bump, release tag, session authentication, grant store, or Trust Tier runtime entered the diff.
