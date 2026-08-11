## MODIFIED Requirements

### Requirement: Install audit logger for sandboxed runs
When `run_council` runs against a project with an initialized sandbox, it SHALL place a versioned audit logger in the single run security context, correlated to the created session. Middleware SHALL own sequenced tool attempt/result audit writes, and session evidence SHALL link to the resulting exact audit event identities. Context cleanup SHALL remove the logger with the rest of the run state, including on failure paths.

#### Scenario: Sandboxed run installs audit logger
- **WHEN** `run_council` starts with an initialized sandbox and creates a session
- **THEN** the active security context has an audit logger for the duration of the run with the same session id

#### Scenario: Middleware supplies session linkage
- **WHEN** a sandboxed tool action emits a versioned attempt and result
- **THEN** its session tool-call record carries the same request/action identifiers and exact attempt/result event IDs without creating a second audit decision

#### Scenario: Audit logger reset after run
- **WHEN** `run_council` completes or fails
- **THEN** no active security context exposes that run's audit logger

#### Scenario: No sandbox skips audit install
- **WHEN** `run_council` runs without an initialized sandbox
- **THEN** its security context has no session writer or audit logger, the run still proceeds, middleware still tracks in memory, and no audit/session files are created
