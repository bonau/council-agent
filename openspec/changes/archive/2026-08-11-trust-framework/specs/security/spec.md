## ADDED Requirements

### Requirement: Trust Tier runtime selects confirmation and optional grant consumption
Product security contexts SHALL carry an explicit Trust Tier of `0`, `1`, or `2` (default `0`). The dispatcher SHALL translate the tier, canonical action risk, and optional exact grant lookup into matrix grant and interaction inputs without reordering matrix version 1 deny precedence. Tier 0 SHALL require confirmation for every risk including read and SHALL NOT skip confirmation via grant. Tier 1 SHALL allow read without confirmation; SHALL allow mutate without confirmation only when an exact matching grant is valid; and SHALL still require confirmation for high-risk after authentication. Tier 2 SHALL auto-approve interaction after authority gates pass, recording a valid grant when present and `trust_grant_not_required` when absent without denying for absence. Selecting Tier 2 SHALL require principal scope `high-risk:manage` and a fresh high-risk step-up authentication before the context is used for product tools. `--yes` and `ConfirmMode` SHALL remain interaction-only and SHALL NOT select a tier or create a grant. Exact grant lookup SHALL occur only on the mandatory dispatcher path.

#### Scenario: Default Tier 0 confirms reads
- **WHEN** a product read tool runs under Tier 0 without automatic confirmation approval
- **THEN** the action requires confirmation and is not executed until interaction allows it

#### Scenario: Tier 1 mutate uses exact grant to skip confirmation
- **WHEN** Tier 1 mutate runs with an exact matching active grant for the principal, action, resource, and required scopes
- **THEN** the matrix grant state is allowed, interaction is treated as automatic approval, and the handler may run without a prompt

#### Scenario: Tier 1 mutate without grant still confirms
- **WHEN** Tier 1 mutate runs and lookup finds no matching grant
- **THEN** grant state is not required, confirmation follows `ConfirmMode`, and `--yes` only supplies automatic interaction

#### Scenario: Invalid grant remains denying under Tier 1
- **WHEN** Tier 1 mutate lookup returns revoked, expired, invalid, or scope-insufficient for the exact action
- **THEN** the matrix denies for the grant reason and confirmation or `--yes` cannot allow the action

#### Scenario: Tier cannot override earlier denial
- **WHEN** policy, scope, or authentication denies an action under any Trust Tier including Tier 2 with `--yes`
- **THEN** the matrix keeps the earlier denial reason and the handler does not run

#### Scenario: Tier 2 selection requires step-up
- **WHEN** a caller requests Trust Tier 2 without fresh high-risk authentication or without `high-risk:manage`
- **THEN** the product path refuses to install or use that Tier 2 context for tools

#### Scenario: Persisted grant is looked up only through the dispatcher
- **WHEN** a product tool action runs under a tier that may consume grants
- **THEN** exact lookup occurs on the mandatory dispatcher path and Crew adapters do not perform a parallel grant decision

## REMOVED Requirements

### Requirement: v0.9.8 does not enable Trust Tier runtime
**Reason**: Superseded by Trust Tier runtime requirements in v1.0-alpha.
**Migration**: Product contexts must set an explicit tier (default 0). Callers that relied on permanent grant disconnect must adopt Tier 0 or accept Tier 1 exact-grant confirmation skipping. CLI gains `--trust-tier`.
