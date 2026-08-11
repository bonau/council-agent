## ADDED Requirements

### Requirement: Install audit logger for sandboxed runs

When `run_council` runs against a project with an initialized sandbox, it SHALL install an audit logger scoped to that run (including the session id when a session is created). The logger SHALL be reset when the run ends, including on failure paths.

#### Scenario: Sandboxed run installs audit logger

- **WHEN** `run_council` starts with an initialized sandbox and creates a session
- **THEN** an audit logger is installed for the duration of the run with that session id available to audit records

#### Scenario: Audit logger reset after run

- **WHEN** `run_council` completes or fails
- **THEN** the audit logger context is reset so subsequent code does not keep writing to that run's logger

#### Scenario: No sandbox skips audit install

- **WHEN** `run_council` runs without an initialized sandbox
- **THEN** no audit logger is installed and the run still proceeds without requiring audit storage
