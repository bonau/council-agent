## ADDED Requirements

### Requirement: Control-plane storage uses restrictive local permissions
Sandbox initialization and evidence writers SHALL request owner-only directory and file permissions for `.council` audit/session control-plane storage on hosts that support POSIX permission modes. Re-initialization SHALL preserve existing evidence while reasserting those modes. These modes SHALL be documented as defense in depth and not as protection from the owning host user or root.

#### Scenario: New control-plane storage is owner-only
- **WHEN** a sandbox, session, or audit file is created on a POSIX host
- **THEN** control-plane directories request mode `0700` and persisted control-plane files request mode `0600`

#### Scenario: Re-init preserves evidence
- **WHEN** sandbox initialization reasserts restrictive permissions
- **THEN** existing audit and session contents remain unchanged

## MODIFIED Requirements

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

#### Scenario: Policy cannot remove control-plane protection
- **WHEN** a valid project policy omits protected paths or declares unrelated `denied_paths`
- **THEN** all built-in control-plane protections remain active

#### Scenario: Policy cannot remove its own protection
- **WHEN** a valid project policy omits its own path or declares unrelated `denied_paths`
- **THEN** built-in protection for every `council.policy.yaml` remains active

#### Scenario: Listing parent directory allowed
- **WHEN** `resolve()` is called with path `.` for `list_dir`
- **THEN** it succeeds even if the directory contains denied entries such as `.env`, `.git`, `.council`, or `council.policy.yaml`

#### Scenario: Tool protection is not OS containment
- **WHEN** code executes outside the modeled product filesystem and shell path actions, including project code run by a test process or a host-user operation
- **THEN** the denylist provides no claim that the operating system prevents that code from modifying control-plane files

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
