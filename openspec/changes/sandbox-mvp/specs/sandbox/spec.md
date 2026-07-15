## ADDED Requirements

### Requirement: Sandbox workspace initialization

The system SHALL provide `council sandbox init` that creates a `.council/` directory in the current working directory (or specified workspace). It SHALL write `.council/config.yaml` with at least `workspace_root`. If `.council/` already exists, init SHALL succeed without deleting existing sessions.

#### Scenario: First-time init

- **WHEN** `council sandbox init` is run in a directory without `.council/`
- **THEN** it creates `.council/config.yaml` and returns success

#### Scenario: Idempotent re-init

- **WHEN** `council sandbox init` is run and `.council/` already exists
- **THEN** it succeeds without removing existing session data

### Requirement: Sandbox status command

The system SHALL provide `council sandbox status` that displays the workspace root, whether `.council/` exists, and summary of the most recent session (id, tool call count, timestamps).

#### Scenario: Status with active sandbox

- **WHEN** `.council/` exists with at least one session
- **THEN** status shows workspace root and the latest session summary

#### Scenario: Status without sandbox

- **WHEN** `.council/` does not exist
- **THEN** status indicates sandbox is not initialized

### Requirement: Session persistence for tool calls

The system SHALL create a session directory `.council/sessions/<session-id>/` for each `council run`. It SHALL write `meta.json` (prompt, preset, timestamps, workspace root) and append each tool invocation to `tools.jsonl` as one JSON object per line.

#### Scenario: Tool call logged

- **WHEN** a tool is invoked during a run with an active session
- **THEN** a JSON line is appended to that session's `tools.jsonl`

#### Scenario: Session metadata written

- **WHEN** a run starts with sandbox initialized
- **THEN** `meta.json` is created with run metadata before tools execute

### Requirement: CLI workspace override

The system SHALL accept `--workspace <path>` on `council run` and sandbox commands to override the workspace root used by `WorkspaceGuard`.

#### Scenario: Workspace flag sets root

- **WHEN** `council run` is invoked with `--workspace /path/to/project`
- **THEN** all tools validate paths against that root
