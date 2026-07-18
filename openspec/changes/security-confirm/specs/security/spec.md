## ADDED Requirements

### Requirement: Confirmation modes

The system SHALL provide confirmation modes of exactly: `ask`, `auto`, `refuse`, and `compat`. The active mode SHALL be readable via a context-scoped confirmation policy. When no product policy is installed, the default mode SHALL be `compat`.

#### Scenario: Default mode is compat

- **WHEN** no confirmation policy has been installed for the current context
- **THEN** the effective confirmation mode is `compat`

#### Scenario: Auto mode allows without prompting

- **WHEN** the active mode is `auto` and confirmation is required for an action
- **THEN** the gate allows the action without invoking an interactive prompt

#### Scenario: Refuse mode denies without prompting

- **WHEN** the active mode is `refuse` and confirmation is required for an action
- **THEN** the gate denies the action without invoking an interactive prompt

### Requirement: Interactive confirmation prompt

When the active mode is `ask` and confirmation is required, the system SHALL prompt the user with a Rich yes/no confirmation defaulting to No. Affirmative answers SHALL allow the action; negative or default answers SHALL deny the action. The prompt function SHALL be injectable for tests.

#### Scenario: Ask mode approves on yes

- **WHEN** mode is `ask` and the confirm function returns True
- **THEN** the confirmation gate allows the action and records outcome `approved`

#### Scenario: Ask mode denies on no

- **WHEN** mode is `ask` and the confirm function returns False
- **THEN** the confirmation gate denies the action and records outcome `denied`

### Requirement: Compat mode preserves v0.6 library defaults

In `compat` mode, confirmation SHALL be required only for shell actions classified as `dangerous` (always denied without prompt). Shell `write` actions and filesystem mutate actions (`write_file`, `delete_file`) SHALL be allowed without prompting.

#### Scenario: Compat refuses dangerous without prompt

- **WHEN** mode is `compat` and a dangerous shell action requests confirmation
- **THEN** the gate denies without prompting

#### Scenario: Compat allows write without prompt

- **WHEN** mode is `compat` and a write shell or filesystem mutate action requests confirmation
- **THEN** the gate allows without prompting

### Requirement: Resolve product confirmation mode from CLI flags

The CLI SHALL resolve product confirmation mode as: `--yes` maps to `auto`; otherwise if stdin is a TTY map to `ask`; otherwise map to `refuse`.

#### Scenario: --yes selects auto

- **WHEN** `council run` is invoked with `--yes`
- **THEN** the resolved confirmation mode is `auto`

#### Scenario: Non-TTY without --yes selects refuse

- **WHEN** `council run` is invoked without `--yes` and stdin is not a TTY
- **THEN** the resolved confirmation mode is `refuse`
