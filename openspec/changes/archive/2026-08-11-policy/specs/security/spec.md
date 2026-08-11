## ADDED Requirements

### Requirement: Policy file schema and validation

The system SHALL support an optional project-root policy file named `council.policy.yaml` whose structure is validated before use. Valid fields for this milestone SHALL include `allowed_commands` (list of patterns), `denied_commands` (list of patterns), and `denied_paths` (list of path patterns). Invalid structure SHALL cause a clear validation error and SHALL NOT silently apply a partial policy. When the file is absent, the system SHALL use built-in defaults without requiring a policy file.

#### Scenario: Valid policy loads successfully

- **WHEN** `council.policy.yaml` contains valid `allowed_commands`, `denied_commands`, and/or `denied_paths` lists
- **THEN** the policy is accepted and available for evaluation

#### Scenario: Invalid policy is rejected

- **WHEN** `council.policy.yaml` has an invalid type for a known field (for example `denied_commands` is a string instead of a list)
- **THEN** loading fails with a validation error and the invalid file is not applied

#### Scenario: Missing policy uses defaults

- **WHEN** no `council.policy.yaml` exists at the project root
- **THEN** the system continues with built-in defaults and does not error solely due to the missing file

### Requirement: Denied command patterns hard-block

When a non-empty `denied_commands` list is active, any shell command that matches a denied pattern SHALL be refused before execution. Refusal SHALL return a structured tool failure (not an uncaught exception) indicating policy denial.

#### Scenario: Denied command is refused

- **WHEN** the active policy denies a pattern such as `curl *` and `run_command` is invoked with `curl https://example.com`
- **THEN** the command is not executed and the tool result indicates policy denial

### Requirement: Allowed command list restricts shell commands

When `allowed_commands` is present and non-empty, a shell command SHALL be allowed by policy only if it matches at least one allowed pattern. Commands that fail the allowlist SHALL be refused before execution even if they would otherwise be classified as `read`. When `allowed_commands` is absent or empty, no allowlist restriction SHALL be applied by the policy layer.

#### Scenario: Command outside allowlist is refused

- **WHEN** the active policy sets `allowed_commands` to patterns such as `pytest *` and `run_command` is invoked with `echo hello`
- **THEN** the command is not executed and the tool result indicates the command is not allowed by policy

#### Scenario: Command matching allowlist proceeds to later gates

- **WHEN** the active policy allows `pytest *` and `run_command` is invoked with `pytest -q`
- **THEN** the policy allowlist check passes and later classification/confirmation gates still apply

#### Scenario: Empty allowlist means no allowlist restriction

- **WHEN** the active policy omits `allowed_commands` or sets it to an empty list
- **THEN** shell commands are not refused solely for failing an allowlist

### Requirement: Policy evaluation order for shell commands

For shell commands, policy evaluation SHALL apply `denied_commands` before `allowed_commands`. A command matching a denied pattern SHALL be refused even if it also matches an allowed pattern.

#### Scenario: Deny wins over allow

- **WHEN** a command matches both a denied pattern and an allowed pattern
- **THEN** the command is refused as denied by policy

### Requirement: Context-scoped active policy

The system SHALL expose a context-scoped active policy for tool and guard evaluation. When no policy is installed, evaluation SHALL behave as built-in defaults (no extra command denials/allowlist; no extra denied paths from policy). Installing and resetting the active policy SHALL be possible for the duration of a product run.

#### Scenario: No installed policy uses built-in defaults

- **WHEN** no product policy is installed in the current context
- **THEN** command policy checks impose no extra deny/allow list beyond built-in classifier/confirmation behavior

#### Scenario: Installed policy is visible to evaluators

- **WHEN** a valid policy is installed for the current context
- **THEN** subsequent command and path evaluations use that policy until it is reset
