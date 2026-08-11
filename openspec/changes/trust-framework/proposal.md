## Why

v0.9.x closed the debt sequence and matrix-v1 contract, but product tools still hard-code `trust_grant_not_required` and expose no Trust Tier 0/1/2 runtime. Alpha admission evidence is complete; Council now needs the ROADMAP Trust Tier behavior wired through the existing dispatcher without reopening deny precedence or treating `--yes` as elevation.

## What Changes

- Add typed Trust Tier 0/1/2 selection on `SecurityContext` and CLI `council run --trust-tier`.
- Add a pure tier→grant/interaction translator that feeds matrix-v1 without changing policy→scope→authentication→grant→risk→interaction precedence.
- Connect explicit `TrustGrantStore.lookup` on the product path when the tier may consume an exact grant (Tier 1 mutate auto-skip; optional Tier 2 evidence).
- Require fresh high-risk step-up (and `high-risk:manage`) to select Tier 2; default remains Tier 0.
- Keep `ConfirmMode` / `--yes` as interaction-only; update help, docs, tests, and release evidence for `v1.0.0-alpha.1`.
- **BREAKING** for callers that assumed grants never affect tools: matching exact grants can now skip mutate confirmation under Tier 1; Tier 0 now confirms read actions as well as mutate/high-risk.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Enable Trust Tier runtime, translator, grant consumption into matrix grant/interaction states, and Tier 2 selection authentication.
- `tools`: Product tool paths honor tier-driven confirmation/grant disposition via the mandatory dispatcher only.
- `orchestration`: CLI/orchestrator accept `--trust-tier`, forward tier into `SecurityContext`, and keep `council trust` as store administration distinct from tier selection.
- `release-prep`: Alpha/beta evidence and handoff update for Trust Tier runtime after admission.

## Impact

Affected areas: `src/council_agent/security/` (new `trust.py`, middleware, context), `cli.py`, `orchestrator.py`, security/tools/orchestration/release-prep specs, tests, README/ROADMAP/testing docs, and `docs/releases/evidence/`. Package version bump stays on `release/1.0.0a1` only.

## Non-goals

- Do not add `trust_tier` to project `council.policy.yaml` (restrict-only closed schema v1 unchanged; policy cannot elevate).
- Do not implement wildcard grants, remote IAM/SSO, OS sandbox, or predecessor-linked / externally anchored audit hash chain (remain GA or later).
- Do not let `--yes`, ConfirmMode, session UUID, or provider API keys select or satisfy Trust Tier / grants.
- Do not bump package version or create release tags on the feature branch.
- Do not implement v1.0 GA remaining DoD items beyond Trust Tier runtime needed for alpha/beta.
