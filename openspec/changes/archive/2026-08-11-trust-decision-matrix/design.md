## Context

See `proposal.md` for motivation. v0.9.5 supplies principal/scope decisions, v0.9.6 supplies exact-action authentication decisions, and v0.9.7 supplies explicit grant lookup decisions, but they currently have no common outcome type. Confirmation is still evaluated inside private filesystem/shell handlers. All supported library and Crew calls already converge on `security.middleware.invoke()`, while CLI only constructs the context used by that dispatcher.

The matrix must be useful to v1.0-alpha without activating Trust Tier state or ambient consumption of the user-owned grant store. It must also preserve current `ask`/`auto`/`refuse`/`compat` behavior for otherwise authorized actions.

## Goals / Non-Goals

**Goals:**

- Provide one pure, immutable, versioned vector/result model with exhaustive enum inputs and stable reasons.
- Make deny precedence independent of `ConfirmMode`, wrapper type, or handler outcome.
- Attach one normalized matrix view to dispatcher result, tracker, session, and audit evidence.
- Keep existing detailed scope/authentication/policy metadata and existing public tool signatures compatible.

**Non-Goals:**

- No Trust Tier enum, tier-to-vector translator, `--trust-tier`, or Tier 0/1/2 runtime state.
- No ambient grant-store read, wildcard authority, new grant schema, or persistent effect from confirmation.
- No redesign of command parsing, WorkspaceGuard, authentication challenge flow, or grant administration.

## Decisions

### Use a pure schema-v1 matrix with closed input states

Add a CrewAI-independent module under `security/` containing:

- `PolicyState`: allowed, denied, not allowed;
- `ScopeState`: allowed plus each existing missing/revoked/invalid/mismatch/insufficient state;
- `AuthenticationState`: not required, satisfied, and every existing denial state;
- `GrantState`: not required, valid, missing/not-found, invalid, revoked, expired, and principal/grant scope insufficient;
- `ActionRisk`: read, mutate, high risk, or unrecognized;
- `InteractionState`: not required, pending, automatic approval, explicit approval, explicit denial, refusal, or compatibility allow;
- `TrustDecisionOutcome`: deny, require confirmation, or allow.

`DecisionVector` validates only these enums. `evaluate_decision()` has no I/O, context access, prompt, store access, or framework dependency and returns an immutable `TrustDecision` with matrix version `1`, one outcome/reason, and JSON-safe evidence.

Alternative considered: reuse `ConfirmMode` as the primary matrix input. Rejected because a mode says how to resolve interaction, not whether earlier authority exists; normalized interaction state also represents an unanswered `ask` result.

Alternative considered: accept arbitrary reason strings. Rejected because misspelled or newly invented security reasons would silently fragment CLI/Crew/library behavior.

### Fix precedence before adding tier translation

Matrix v1 uses this order:

| Priority | Input | Denying states | Result reason |
|---:|---|---|---|
| 1 | policy | denied, not allowed | `policy_denied`, `policy_not_allowed` |
| 2 | scope | any state except allowed | existing `principal_*` / `scope_insufficient` code |
| 3 | authentication | any required state except satisfied | existing `authentication_*` code |
| 4 | grant | any required/present state except valid | existing `trust_grant_*` code |
| 5 | action risk | unrecognized | `action_risk_unrecognized` |
| 6 | interaction | pending, denied, refused | `confirmation_required`, `confirmation_denied`, `confirmation_refused` |
| 7 | completed path | all preceding inputs pass | `decision_allowed` |

Read risk needs no interaction. Mutate/high-risk actions reach interaction only after authority gates pass. Pending interaction returns `require_confirmation`; approved, automatic, and compatibility-allow states return `allow`. The matrix itself never calls a prompt.

Alternative considered: let `auto` or a future tier be checked before authentication/grant. Rejected because that turns an interaction preference into authority and recreates V1-009/SEC-P0-005.

### Normalize current subsystem decisions at the mandatory dispatcher

The dispatcher maps existing `ScopeDecision` and `AuthenticationDecision` reasons directly into closed matrix states. It normalizes project command-policy metadata and the handler's confirmation outcome, derives risk from the canonical product tool/classification, and sets grant state to `not_required` for all v0.9.8 product contexts. It then evaluates the pure matrix and adds `trust_decision` metadata containing version, vector, outcome, and winning reason.

For authority refusals that occur before a handler, the dispatcher evaluates the same matrix before final evidence. For otherwise authorized operations, it normalizes the handler's already-resolved policy/confirmation evidence. Ordinary operational failures remain security-allowed actions: `ToolResult.success` can be false while the matrix outcome is `allow`. Pre-execution malformed/unsupported actions use unrecognized risk and remain denied without misrepresenting an interaction decision.

Tracker/session/audit already consume dispatcher result metadata, so they receive the same matrix object without a second writer. Crew adapters continue formatting only; CLI continues supplying a context only. This yields entry-point equivalence without placing CrewAI in `tools/` or calling tools from `cli.py`.

Alternative considered: duplicate matrix calls in CLI and Crew wrappers. Rejected because it would create three decision paths and conflicting audit reasons.

### Preserve detailed legacy evidence alongside the normalized reason

Existing `rejection_reason`, `scope_authorization`, `session_authentication`, policy, classification, and confirmation metadata remain available. `metadata.decision` is set from the normalized matrix when the matrix resolves authority; `metadata.trust_decision.reason` is the stable cross-entry reason. Handler success/failure never supplies authority fields and cannot overwrite dispatcher correlation or matrix evidence.

This is additive compatibility. Consumers that currently inspect a detailed legacy reason continue to work, while future tier wiring consumes the matrix vector/result.

### Keep `ConfirmMode` behavior but make its boundary explicit

The current confirmation evaluator remains responsible for prompts and current compatibility behavior. Its result is translated only at the final interaction dimension:

- `AUTO` → automatic approval;
- `ASK` without response → pending, then approved/denied after the prompt;
- `REFUSE` → refused;
- `COMPAT` → compatibility allow for mutate and refusal for high risk;
- read → interaction not required.

CLI help states that `--yes` skips prompts only and cannot grant scopes, authenticate, create grants, or elevate privilege. Tests combine `--yes`/`AUTO` with every earlier denial category and assert no prompt/handler/process/side effect.

## Risks / Trade-offs

- [Normalized evidence could disagree with a legacy handler reason] → Centralize mapping in the dispatcher, validate closed enums, and add assertions covering every mapping and winning reason.
- [Adding metadata changes exact-dictionary tests] → Keep existing keys/values and add one namespaced `trust_decision` object; update only tests that intentionally assert the full contract.
- [Grant state could be mistaken for active grant consumption] → Runtime always records `not_required`, never opens the store, and documents that future tier wiring must explicitly supply a lookup result.
- [A future new subsystem reason is not mapped] → Fail closed as an unrecognized action/state and require an explicit matrix-version review rather than accepting an arbitrary string.
- [Confirmation prompts still occur in private handlers] → The dispatcher remains the sole product evidence owner; v0.9.8 normalizes the resolved interaction and does not introduce a second execution path.

## Migration Plan

1. Add the pure enums, vector/result model, precedence evaluator, exhaustive table tests, and serialization tests.
2. Add dispatcher normalization and result/audit evidence tests for policy, scope, authentication, grant-contract, risk, and interaction states.
3. Verify direct library, Crew adapter, and CLI-resolved contexts yield equivalent vectors/reasons; verify `--yes` denial and no-side-effect cases.
4. Update CLI help and release-preparation evidence, sync specs, validate, archive, and run the full gate.
5. Rollback removes additive matrix metadata/module and restores the prior dispatcher correlation. No persisted state requires migration because v0.9.8 writes no Trust Tier or grant-consumption state.
