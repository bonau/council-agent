## ADDED Requirements

### Requirement: Structured audit log records

The system SHALL support appending structured audit records for tool invocations. Each record SHALL include: a UTC timestamp, tool name, arguments, success boolean, optional error message, metadata (JSON-serializable), and optional session id identifying the caller run. When no audit logger is installed for the current context, recording SHALL be a no-op.

#### Scenario: Record includes required fields

- **WHEN** an audit logger is installed and a tool invocation is recorded
- **THEN** the appended record includes timestamp, tool name, arguments, success, and session id when available

#### Scenario: No logger is a no-op

- **WHEN** no audit logger is installed and a record is requested
- **THEN** no file is written and no error is raised

### Requirement: Append-only audit storage under .council

When sandbox is initialized, audit events SHALL be stored as append-only JSON Lines under `.council/audit/` (default file `events.jsonl`) within the project root. Existing lines SHALL NOT be rewritten by normal append operations.

#### Scenario: Events append to JSONL file

- **WHEN** multiple tool invocations are audited for an initialized sandbox
- **THEN** each event is appended as one JSON object line in `.council/audit/events.jsonl`

#### Scenario: Prior events remain intact

- **WHEN** a new audit event is appended after prior events exist
- **THEN** previously written lines remain unchanged

### Requirement: Argument truncation in audit records

String argument values that exceed a fixed size limit SHALL be truncated in the stored audit record with an explicit truncation marker. Truncation SHALL NOT change the actual tool execution arguments.

#### Scenario: Large string arg truncated in audit only

- **WHEN** a tool is invoked with a string argument larger than the audit size limit
- **THEN** the audit record stores a truncated value with a truncation marker while the tool still receives the full argument

### Requirement: council audit show

The CLI SHALL provide `council audit show` that displays recent audit events from the project audit log (newest or file order with a configurable limit). It SHALL support filtering by session id and a `--workspace` root override. When the audit log is missing or empty, the command SHALL report that there are no events without crashing.

#### Scenario: Show recent events

- **WHEN** `council audit show` is run for a project with existing audit events
- **THEN** the CLI displays audit entries including timestamp, tool name, success, and session id

#### Scenario: Empty audit log

- **WHEN** `council audit show` is run and no audit events exist
- **THEN** the CLI reports that there are no events and exits successfully

### Requirement: council audit export

The CLI SHALL provide `council audit export` that writes audit events to a user-specified output path. Export SHALL support optional session filtering. The default export format SHALL be JSON Lines.

#### Scenario: Export all events as JSONL

- **WHEN** `council audit export` is run with an output path and events exist
- **THEN** the output file contains one JSON object per line for each exported event

#### Scenario: Export filtered by session

- **WHEN** `council audit export` is run with a session filter
- **THEN** only events matching that session id are written to the output file
