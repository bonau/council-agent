## ADDED Requirements

### Requirement: run_command applies project policy before execution

`run_command` SHALL evaluate the active project policy against the command string before starting the subprocess. Policy denial (denied pattern or failed allowlist) SHALL return `success=False` with an error describing the policy decision, and SHALL NOT execute the command. Policy checks SHALL occur before confirmation prompts for the same command.

#### Scenario: Policy-denied command does not run

- **WHEN** `run_command` is called with a command matching an active `denied_commands` pattern
- **THEN** the result has `success=False`, the error mentions policy denial, and no subprocess is started

#### Scenario: Policy check precedes confirmation

- **WHEN** a command would require confirmation and also matches a denied policy pattern
- **THEN** the tool returns a policy denial without prompting for confirmation

#### Scenario: Allowed-by-policy command still subject to classification

- **WHEN** a command passes policy allow/deny checks and matches a dangerous classification pattern
- **THEN** the existing classification and confirmation gates still apply
