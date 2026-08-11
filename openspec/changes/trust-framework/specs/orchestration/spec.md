## ADDED Requirements

### Requirement: CLI and orchestrator forward Trust Tier into the security context
`council run` SHALL accept `--trust-tier` with values `0`, `1`, or `2` and default to `0`. Orchestration SHALL place the selected tier on the single product `SecurityContext` used for planning, execution, verification, and escalation. Selecting Tier 2 SHALL perform high-risk step-up authentication before tools run. `--yes` SHALL continue to resolve only to `ConfirmMode.AUTO` and SHALL NOT imply Tier 2. `council trust grant|revoke|list` SHALL remain user-owned store administration and SHALL NOT set the runtime Trust Tier.

#### Scenario: --trust-tier is exposed and defaults to zero
- **WHEN** a user inspects `council run --help` or runs without `--trust-tier`
- **THEN** the option is documented and the installed product context uses Tier 0

#### Scenario: --yes is not Tier 2
- **WHEN** `council run --yes` is used without `--trust-tier 2`
- **THEN** confirmation mode is AUTO, trust tier remains the selected or default tier, and help text states that `--yes` does not elevate privilege

#### Scenario: Tier 2 without verifier fails closed
- **WHEN** `council run --trust-tier 2` is requested without a configured high-risk authentication verifier
- **THEN** the run fails before tool side effects with an authentication-related refusal
