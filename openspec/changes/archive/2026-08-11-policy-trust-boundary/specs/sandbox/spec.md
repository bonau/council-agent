## MODIFIED Requirements

### Requirement: Sensitive path denylist
The system SHALL reject direct access to sensitive paths via a built-in denylist. Denied patterns SHALL include `.env`, `.git`, `.git/**`, `.council/secrets`, `.council/secrets/**`, and project policy files named `council.policy.yaml` at the workspace root or below it. These built-in entries SHALL remain effective regardless of project-policy contents.

#### Scenario: Direct access to .env blocked

- **WHEN** `resolve()` is called with path `.env` or any path matching the denylist
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

#### Scenario: Direct access to .git blocked

- **WHEN** `resolve()` is called with path `.git` or `.git/config`
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

#### Scenario: Root project policy access blocked

- **WHEN** a product filesystem tool or a supported shell path action resolves root path `council.policy.yaml`
- **THEN** path validation denies the action before reading, writing, deleting, or starting a subprocess

#### Scenario: Nested project policy access blocked

- **WHEN** a product filesystem tool or a supported shell path action resolves a nested path ending in `/council.policy.yaml`
- **THEN** path validation denies the action before reading, writing, deleting, or starting a subprocess

#### Scenario: Policy cannot remove its own protection

- **WHEN** a valid project policy omits its own path or declares unrelated `denied_paths`
- **THEN** built-in protection for every `council.policy.yaml` remains active

#### Scenario: Listing parent directory allowed

- **WHEN** `resolve()` is called with path `.` for `list_dir`
- **THEN** it succeeds even if the directory contains denied entries such as `.env`, `.git`, or `council.policy.yaml`

#### Scenario: Tool protection is not OS containment

- **WHEN** code executes outside the modeled product filesystem and shell path actions, including project code run by a test process or a host-user operation
- **THEN** the denylist provides no claim that the operating system prevents that code from modifying the policy file
