# Sandbox

## Purpose

Workspace boundary enforcement and local sandbox session management. Introduced in v0.3 via `WorkspaceGuard`; v0.5 adds `.council/` initialization, session persistence, and `council sandbox` CLI.

## Requirements

### Requirement: WorkspaceGuard path boundary validation

The system SHALL provide a `WorkspaceGuard` class that validates file paths and working directories against a workspace root. All resolved paths SHALL remain within the workspace root after `Path.resolve()` (including symlink expansion).

#### Scenario: Path within workspace

- **WHEN** `resolve()` is called with a relative or absolute path whose resolved location is inside the workspace root
- **THEN** it returns the resolved `Path` without error

#### Scenario: Path traversal blocked

- **WHEN** `resolve()` is called with a path containing `../` that resolves outside the workspace root
- **THEN** it raises `WorkspaceGuardError` with a descriptive message

#### Scenario: Symlink escape blocked

- **WHEN** `resolve()` is called with a symlink that points outside the workspace root
- **THEN** it raises `WorkspaceGuardError` with a descriptive message

#### Scenario: Symlink within workspace allowed

- **WHEN** `resolve()` is called with a symlink that points to a location inside the workspace root
- **THEN** it returns the resolved `Path` without error

### Requirement: Sensitive path denylist

The system SHALL reject direct access to sensitive paths via a default denylist. Denied patterns SHALL include `.env`, `.git`, `.git/**`, `.council/secrets`, and `.council/secrets/**`.

#### Scenario: Direct access to .env blocked

- **WHEN** `resolve()` is called with path `.env` or any path matching the denylist
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

#### Scenario: Direct access to .git blocked

- **WHEN** `resolve()` is called with path `.git` or `.git/config`
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

#### Scenario: Listing parent directory allowed

- **WHEN** `resolve()` is called with path `.` (workspace root) for `list_dir`
- **THEN** it succeeds even if the directory contains `.env` or `.git` entries

### Requirement: Workspace root configuration

The system SHALL support `COUNCIL_WORKSPACE_ROOT` environment variable to set the workspace root. When unset, the default SHALL be the current working directory (`Path.cwd()`).

#### Scenario: Default workspace root

- **WHEN** `COUNCIL_WORKSPACE_ROOT` is not set
- **THEN** the workspace root is the process current working directory at settings load time

#### Scenario: Custom workspace root

- **WHEN** `COUNCIL_WORKSPACE_ROOT` is set to an absolute path
- **THEN** `WorkspaceGuard` uses that path as the workspace root

### Requirement: resolve_cwd for shell commands

The system SHALL provide `resolve_cwd(cwd: str | None) -> Path` that validates working directories for `run_command`. When `cwd` is `None`, it SHALL return the workspace root.

#### Scenario: Default cwd is workspace root

- **WHEN** `resolve_cwd(None)` is called
- **THEN** it returns the workspace root path

#### Scenario: Custom cwd within workspace

- **WHEN** `resolve_cwd` is called with a path inside the workspace root
- **THEN** it returns the resolved path

#### Scenario: Cwd outside workspace blocked

- **WHEN** `resolve_cwd` is called with a path outside the workspace root
- **THEN** it raises `WorkspaceGuardError`

### Requirement: Non-existent path validation for writes

When resolving a path that does not yet exist, the system SHALL validate that the resolved parent directory is within the workspace root and that the intended relative path is not denied.

#### Scenario: Write to new file in workspace

- **WHEN** `resolve()` is called with a path to a non-existent file whose parent is inside the workspace and not denied
- **THEN** it returns the resolved path without error

#### Scenario: Write to denied path blocked

- **WHEN** `resolve()` is called with a path to create `.env` in the workspace
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

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
