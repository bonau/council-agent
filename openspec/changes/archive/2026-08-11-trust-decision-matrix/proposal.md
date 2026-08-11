## Why

`ConfirmMode.AUTO` currently describes an automatic answer to an interaction gate but can be mistaken for authority. Before Trust Tier runtime is introduced, Council needs one reviewable, fail-closed matrix that separates authority inputs from interaction and gives every product entry point the same stable decision and reason.

## What Changes

- Add a versioned, pure decision-matrix contract covering policy, principal/scope, authentication, trust-grant applicability, action risk, and confirmation interaction.
- Define explicit deny precedence and normalized `deny`, `require_confirmation`, and `allow` outcomes with stable reason codes.
- Route product-tool decision evidence through that contract so library and Crew calls, including contexts configured by CLI, report the same decision vector and reason.
- Keep `ConfirmMode` limited to prompt/automatic/refusal behavior; document and test that `--yes` selects interaction behavior only and cannot create or replace principal, scope, authentication, or a trust grant.
- Add table-driven, bypass, no-side-effect, entry-point-equivalence, documentation, and regression evidence.
- Update the v1 preparation known-issues, learning log, handoff, and v0.9.8 evidence documents.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Define the versioned trust decision vector, precedence, stable reasons, confirmation separation, and auditable normalized result.
- `tools`: Require all direct and Crew product-tool paths to expose the same matrix result without a parallel authority path.
- `orchestration`: Clarify that CLI `--yes` supplies only `ConfirmMode.AUTO` and that orchestration does not synthesize authority from interaction state.

## Impact

Affected areas are `src/council_agent/security/`, the mandatory dispatcher, internal filesystem/shell authorization helpers, Crew tool adapter evidence, CLI help/documentation, security and integration tests, and release-preparation documents. No dependency, persistent grant schema, package version, or public Trust Tier setting is added.

## Non-goals

- Do not enable Trust Tier 0/1/2 runtime behavior or add a `--trust-tier` CLI option; that remains v1.0-alpha work.
- Do not add grant types, remote policy, role hierarchy, or connect persisted grants as ambient runtime elevation.
- Do not convert an interactive approval or `--yes` into a persistent grant, principal, scope, or authentication proof.
- Do not bump the package version or create a release tag on this feature branch.
