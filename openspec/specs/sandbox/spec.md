# Sandbox

## Purpose

Workspace boundary enforcement and local sandbox session management. Introduced in v0.3 via `WorkspaceGuard`; v0.5 adds `.council/` initialization, session persistence, and `council sandbox` CLI; v0.8 adds audit directory lifecycle alongside sessions; v0.9 merges project policy `denied_paths` into WorkspaceGuard.

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

The system SHALL reject direct access to security control-plane paths via a built-in denylist. Denied patterns SHALL include `.env`, `.git`, `.git/**`, `.council/secrets/**`, `.council/audit/**`, `.council/sessions/**`, `.council/config.yaml`, reserved `.council/auth/**` and `.council/grants/**` paths, and project policy files named `council.policy.yaml` at the workspace root or below it. Directory roots and nested-project forms of each control-plane path SHALL also be denied. These built-in entries SHALL remain effective regardless of project-policy contents.

#### Scenario: Direct access to .env blocked

- **WHEN** `resolve()` is called with path `.env` or any path matching the denylist
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

#### Scenario: Direct access to .git blocked

- **WHEN** `resolve()` is called with path `.git` or `.git/config`
- **THEN** it raises `WorkspaceGuardError` indicating the path is denied

#### Scenario: Audit and session control planes are blocked

- **WHEN** a product filesystem tool or supported shell path action resolves an audit file, session file, or either directory root under a root or nested `.council/`
- **THEN** path validation denies the action before reading, writing, moving, copying, deleting, or starting a subprocess

#### Scenario: Sandbox configuration and reserved authorization paths are blocked

- **WHEN** a product path action targets `.council/config.yaml`, `.council/auth/**`, or `.council/grants/**`
- **THEN** built-in path validation denies the target even when the path does not yet exist

#### Scenario: Root project policy access blocked

- **WHEN** a product filesystem tool or a supported shell path action resolves root path `council.policy.yaml`
- **THEN** path validation denies the action before reading, writing, deleting, or starting a subprocess

#### Scenario: Nested project policy access blocked

- **WHEN** a product filesystem tool or a supported shell path action resolves a nested path ending in `/council.policy.yaml`
- **THEN** path validation denies the action before reading, writing, deleting, or starting a subprocess

#### Scenario: Policy cannot remove its own protection

- **WHEN** a valid project policy omits its own path or declares unrelated `denied_paths`
- **THEN** built-in protection for every `council.policy.yaml` remains active

#### Scenario: Policy cannot remove control-plane protection

- **WHEN** a valid project policy omits protected paths or declares unrelated `denied_paths`
- **THEN** all built-in control-plane protections remain active

#### Scenario: Listing parent directory allowed

- **WHEN** `resolve()` is called with path `.` for `list_dir`
- **THEN** it succeeds even if the directory contains denied entries such as `.env`, `.git`, `.council`, or `council.policy.yaml`

#### Scenario: Tool protection is not OS containment

- **WHEN** code executes outside the modeled product filesystem and shell path actions, including project code run by a test process or a host-user operation
- **THEN** the denylist provides no claim that the operating system prevents that code from modifying control-plane files

### Requirement: Control-plane storage uses restrictive local permissions

Sandbox initialization and evidence writers SHALL request owner-only directory and file permissions for `.council` audit/session control-plane storage on hosts that support POSIX permission modes. Re-initialization SHALL preserve existing evidence while reasserting those modes. These modes SHALL be documented as defense in depth and not as protection from the owning host user or root.

#### Scenario: New control-plane storage is owner-only

- **WHEN** a sandbox, session, or audit file is created on a POSIX host
- **THEN** control-plane directories request mode `0700` and persisted control-plane files request mode `0600`

#### Scenario: Re-init preserves evidence

- **WHEN** sandbox initialization reasserts restrictive permissions
- **THEN** existing audit and session contents remain unchanged

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

The system SHALL create a protected session directory `.council/sessions/<session-id>/` for each sandboxed `council run`. It SHALL write `meta.json` with sanitized prompt, preset, timestamps, and workspace root and append each tool invocation to `tools.jsonl` as one sanitized JSON object per line. Tool-call entries SHALL preserve middleware request/action identifiers and, when durable audit is active, the exact attempt and result event IDs.

#### Scenario: Tool call logged

- **WHEN** a tool is invoked during a run with an active session
- **THEN** a sanitized JSON line is appended to that session's `tools.jsonl`

#### Scenario: Session metadata written

- **WHEN** a run starts with sandbox initialized
- **THEN** sanitized `meta.json` is created with run metadata before tools execute

#### Scenario: Tool call logged without secrets

- **WHEN** a tool invocation contains a recognized secret in arguments, metadata, output, or error
- **THEN** one JSON line is appended with the secret replaced and the operational result and correlation retained

#### Scenario: Session metadata written without secrets

- **WHEN** a run starts with sandbox initialized and its prompt contains a recognized secret
- **THEN** `meta.json` is created before tools execute with a sanitized prompt

#### Scenario: Session record links audit evidence

- **WHEN** middleware completes a sandboxed action with durable audit enabled
- **THEN** the session tool-call entry identifies the same request/action and exact audit attempt/result event IDs

### Requirement: CLI workspace override

The system SHALL accept `--workspace <path>` on `council run` and sandbox commands to override the workspace root used by `WorkspaceGuard`.

#### Scenario: Workspace flag sets root

- **WHEN** `council run` is invoked with `--workspace /path/to/project`
- **THEN** all tools validate paths against that root

### Requirement: Audit directory created with sandbox init

Sandbox initialization SHALL ensure `.council/audit/` exists under the project root (idempotently). Initialization SHALL NOT delete existing audit events.

#### Scenario: Init creates audit directory

- **WHEN** `council sandbox init` (or equivalent init API) runs on a project
- **THEN** `.council/audit/` exists afterward

#### Scenario: Re-init preserves audit events

- **WHEN** sandbox init runs again on a project that already has audit events
- **THEN** existing audit event files remain intact

### Requirement: Audit log distinct from session tool logs

Session persistence under `.council/sessions/<id>/tools.jsonl` SHALL remain the per-run operational tool log. The audit log under `.council/audit/` SHALL be the cross-session security audit trail. Both MAY record the same invocation without replacing each other.

#### Scenario: Session and audit both retain records

- **WHEN** a tool runs during a sandboxed council run
- **THEN** the invocation may appear in the session `tools.jsonl` and also as an audit event under `.council/audit/`

### Requirement: WorkspaceGuard merges policy denied paths

When an active policy provides `denied_paths`, `WorkspaceGuard` path validation SHALL reject paths matching either the built-in default sensitive denylist or any pattern from the policy `denied_paths` list (union). Built-in defaults SHALL remain in effect even when a policy file is present. Policy patterns SHALL use the same matching semantics as the existing sensitive-path denylist (including `/**` directory prefixes and basename-style patterns).

#### Scenario: Policy denied path is blocked

- **WHEN** the active policy includes `denied_paths` with `secrets/**` and `resolve` is called with `secrets/token.txt`
- **THEN** access is denied as a sensitive path

#### Scenario: Default denylist still applies with policy

- **WHEN** a policy file is active that does not list `.env` in `denied_paths` and `resolve` is called with `.env`
- **THEN** access is still denied by the built-in default denylist

#### Scenario: No policy adds no extra path denials

- **WHEN** no policy is installed
- **THEN** path validation uses only the built-in default denylist patterns
