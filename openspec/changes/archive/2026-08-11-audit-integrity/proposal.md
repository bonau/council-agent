## Why

Audit and session evidence currently lives inside the Agent workspace, can be targeted through supported filesystem or shell actions, and persists secrets with truncation but no real redaction. Audit records also lack a versioned, canonical sequence/identity envelope, so missing, duplicated, partial, or modified events cannot be distinguished reliably from normal history before v1.0 integrity work.

## What Changes

- Protect audit, session, sandbox configuration, project policy, and reserved authentication/grant control-plane paths with built-in `WorkspaceGuard` denied patterns that project policy cannot remove.
- Apply one recursive redaction pipeline to audit and session persistence, covering sensitive field names and common API key, bearer token, JWT, provider token, credential-assignment, and private-key content patterns before truncation or disk writes.
- Introduce a versioned canonical audit envelope with monotonic sequence numbers and deterministic content-derived event IDs; strict loading detects malformed/truncated lines, gaps, duplicates, reordering, unsupported envelopes, and event-content changes.
- Strengthen middleware attempt/result evidence by making result records reference the exact attempt event ID and validating request/action/tool/session correlation.
- Expose audit integrity status through `council audit show` and `export`, while treating legacy events as readable but explicitly unverified.
- Harden control-plane directory/file permissions where the host supports POSIX modes and document the remaining host-user, external-process, test-process, and tail-deletion limits.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Define redacted, sequenced, content-addressed audit envelopes, strict integrity validation, stronger attempt/result linkage, and integrity-aware CLI output.
- `sandbox`: Expand immutable built-in control-plane path protection and sanitize/protect persisted session records.
- `orchestration`: Carry exact attempt-event correlation through middleware-owned result and session evidence.
- `tools`: Require supported filesystem and shell paths to reject control-plane targets without side effects.

## Non-goals

- No complete hash-chain product claim, externally anchored checkpoint, external signature service, hardware key, remote immutable storage, or SIEM integration.
- No claim that the local host user, root, malicious project code executed by `run_tests`, arbitrary external processes, or wholesale log replacement cannot alter control-plane files.
- No Trust Tier behavior, trust decision matrix, grant lifecycle/store, principal or scope model, session authentication, step-up flow, or authorization semantics.
- No package version bump, release tag, or release-branch work.

## Impact

The change updates `security/audit.py`, `security/middleware.py`, `sandbox/workspace.py`, `sandbox/config.py`, `sandbox/session.py`, audit CLI presentation, and their unit/integration tests. Stored audit records gain an explicit schema version, sequence, event ID, and attempt reference; legacy records remain readable only as `legacy_unverified`. Main `security`, `sandbox`, `orchestration`, and `tools` specs plus v0.9.4 evidence, known-issues, learning-log, and handoff documentation are updated. No dependency is added.
