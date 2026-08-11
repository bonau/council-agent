## ADDED Requirements

### Requirement: Orchestrator installs independent authentication state

The orchestrator SHALL create a non-empty runtime session identifier for every run, SHALL enable the security context's high-risk step-up requirement, and SHALL install optional process-local authentication state in the same security-context lifecycle while keeping it distinct from the Council principal, provider credential, project policy, confirmation policy, and persisted session writer. Cleanup SHALL revoke and remove the run's outstanding authentication state on success and failure.

#### Scenario: Sandboxed run binds authentication to persisted session

- **WHEN** a sandboxed run configures a service verifier
- **THEN** authentication binds to the same session identifier used for audit/session correlation without storing authentication credentials in that session

#### Scenario: Non-sandbox run has runtime session binding

- **WHEN** a run has no initialized sandbox
- **THEN** it still has a process-local runtime session identifier for authentication binding while writing no session files

#### Scenario: Cleanup invalidates outstanding state

- **WHEN** a run completes or raises after creating authentication challenges or tokens
- **THEN** its authentication manager is revoked and a later run cannot consume those outstanding values

### Requirement: CLI service authentication is typed and non-interactive

The CLI SHALL optionally load a Council authentication verifier from a dedicated secret setting independent of `OPENROUTER_API_KEY`, principal configuration, and command-line arguments. When configured, the orchestrator SHALL use it to produce a new exact-action challenge response and one-use step-up token for each high-risk action. The CLI SHALL display only whether step-up authentication is configured and SHALL NOT display the verifier or generated proof values.

#### Scenario: Configured verifier supports automated step-up

- **WHEN** a non-interactive run has a valid dedicated authentication verifier and requests a scoped high-risk action
- **THEN** the action receives fresh exact-action step-up evidence and proceeds to remaining policy/confirmation gates

#### Scenario: Missing verifier fails closed only where required

- **WHEN** no authentication verifier is configured
- **THEN** ordinary scoped actions remain compatible and high-risk actions are denied for missing authentication

#### Scenario: Authentication input remains separate

- **WHEN** the CLI loads provider credential, principal settings, confirmation flags, and authentication verifier
- **THEN** each value follows its dedicated data flow and none synthesizes or expands another

### Requirement: Confirmation flags never authenticate

`--yes` and confirmation mode SHALL only select confirmation behavior. They SHALL NOT create an authentication manager, answer a challenge, issue or consume a step-up token, satisfy freshness, or override an authentication denial.

#### Scenario: --yes without authentication is denied

- **WHEN** `council run --yes` reaches a scoped high-risk action without a configured verifier or matching fresh proof
- **THEN** the action is denied before confirmation and no filesystem or subprocess side effect occurs

#### Scenario: Authentication does not bypass confirmation policy

- **WHEN** a high-risk action has valid fresh authentication but confirmation mode refuses or project policy denies it
- **THEN** the action remains denied by that later gate
