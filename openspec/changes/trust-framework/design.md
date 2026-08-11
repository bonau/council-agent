## Context

Matrix-v1 (`security/decision.py`) and user-owned `TrustGrantStore` already exist. Middleware `_runtime_trust_decision` hard-codes `GrantState.NOT_REQUIRED` and never opens the store. Alpha admission on `v0.9.9` is complete. This change enables ROADMAP Trust Tier 0/1/2 through the existing choke point only.

## Goals / Non-Goals

**Goals:**

- Typed `TrustTier` on product context + CLI `--trust-tier {0,1,2}` (default 0).
- Pure translator mapping tier + risk + optional exact lookup → closed `GrantState` + confirmation intent.
- Explicit store lookup from the dispatcher; no ambient second path.
- Tier 2 selection requires `high-risk:manage` + fresh step-up authentication.
- Preserve matrix deny precedence; `--yes` remains interaction-only.

**Non-Goals:**

- Project-policy `trust_tier` field, wildcards, hash chain, OS sandbox, remote IAM.
- Changing grant store schema or `council trust` admin semantics beyond documenting runtime consumption.

## Decisions

### Tier translator (matrix-v1 compatible)

| Tier | Risk | Grant disposition | Interaction intent |
|---|---|---|---|
| 0 | any | `NOT_REQUIRED` (no skip-via-grant) | Always require confirmation (including read) |
| 1 | read | `NOT_REQUIRED` | Auto (no confirm) |
| 1 | mutate | lookup: allowed→`VALID`+auto; not found→`NOT_REQUIRED`+confirm; revoked/expired/invalid/insufficient→that deny state |
| 1 | high_risk | `NOT_REQUIRED` | Confirm after step-up auth (grant does not skip) |
| 2 | any | allowed→`VALID`; else `NOT_REQUIRED` (missing/revoked do not deny) | Auto after authority |

Tier 2 **selection** is itself high-risk: orchestrator/CLI must obtain fresh step-up before installing a Tier 2 context. Invalid store I/O still fails closed.

### Context fields

`SecurityContext` gains `trust_tier: TrustTier` (default 0) and optional `trust_grant_store: TrustGrantStore | None`. Product `run_council` constructs a store bound to the workspace when sandbox/user trust root is usable; lookup failures that are “not found” are soft; ownership/mode failures deny the action that needed the store.

### Confirmation for Tier 0 reads

Filesystem/shell read paths currently skip confirmation. Dispatcher applies tier intent: when translator requires confirmation for read, invoke the same confirmation gate used for mutate (ASK/AUTO/REFUSE/COMPAT) before handler execution.

### CLI

- `council run --trust-tier N` with N in `{0,1,2}`; default 0.
- Help states `--trust-tier` is independent of `--yes` and of `council trust` store admin.
- Reject unknown values; do not accept policy-file tier.

### Evidence

`metadata.trust_decision` continues to carry matrix-v1 vector. Add non-secret `metadata.trust_tier` and retain existing grant lookup metadata when a lookup runs. No matrix version bump unless a new reason code is required (not expected).

## Risks / Trade-offs

- [Tier 0 confirms reads] → Document as intentional alpha behavior; CI can use `--yes` with Tier 0 for auto-approve interaction only.
- [Grant lookup latency/ownership fail-closed] → Same as v0.9.7 store rules; tests cover missing root and revoke.
- [Tier 2 step-up UX] → Fail closed with `authentication_missing` when secret unset; no silent Tier 2.

## Migration Plan

1. Pure `trust.py` + unit tests.
2. Middleware/context wiring + library tests.
3. CLI/orchestrator + Crew parity tests.
4. Docs/evidence; sync/archive; release on `release/1.0.0a1` only.

Rollback removes tier fields and restores `GrantState.NOT_REQUIRED` disconnect; grant store files remain valid.
