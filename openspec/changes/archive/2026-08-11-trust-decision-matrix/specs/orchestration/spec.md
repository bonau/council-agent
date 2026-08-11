## ADDED Requirements

### Requirement: CLI interaction flags do not create authority
The CLI SHALL describe and pass `--yes` solely as the selection of non-prompting `ConfirmMode.AUTO` interaction behavior. CLI and orchestration SHALL resolve principal/scopes, authentication configuration, project policy, and any future grant input through separate typed data flows. Neither `--yes`, TTY state, nor confirmation callbacks SHALL synthesize or expand another decision-vector dimension.

#### Scenario: --yes preserves missing-scope denial
- **WHEN** `council run --yes` configures a principal that lacks a required action scope
- **THEN** the action is denied for the stable scope reason before interaction and no operation runs

#### Scenario: --yes preserves missing-authentication denial
- **WHEN** `council run --yes` reaches a high-risk action without a valid exact-action step-up proof
- **THEN** the action is denied for the stable authentication reason before interaction and no operation runs

#### Scenario: CLI help states the boundary
- **WHEN** a user reads help for `council run --yes`
- **THEN** the text states that it skips interaction prompts only and does not grant scopes, authenticate, create a trust grant, or elevate privilege

### Requirement: Orchestration contexts use the shared matrix contract
An orchestration-created security context SHALL supply the same policy, principal/scope, authentication, grant-default, action-risk, and interaction semantics used by direct library and Crew product paths. Orchestration SHALL NOT translate confirmation mode into Trust Tier state, and v0.9.8 SHALL NOT accept a Trust Tier runtime setting.

#### Scenario: CLI-configured and library-configured vectors agree
- **WHEN** equivalent CLI and direct-library contexts reach the same canonical action with the same six decision dimensions
- **THEN** dispatcher evidence reports the same normalized outcome and stable reason

#### Scenario: No Trust Tier setting is forwarded
- **WHEN** orchestration creates a v0.9.8 security context
- **THEN** it contains no Tier 0/1/2 selection and no `--trust-tier` value
