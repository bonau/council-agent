## ADDED Requirements

### Requirement: Public tool APIs dispatch before execution
The public `read_file`, `write_file`, `list_dir`, `delete_file`, `run_command`, and `run_tests` APIs SHALL send their canonical tool name and typed arguments to the mandatory policy dispatcher. They SHALL NOT perform filesystem access, subprocess creation, policy/confirmation decisions, tracking, session persistence, or audit persistence on a parallel public path.

#### Scenario: Direct library API is dispatcher-backed
- **WHEN** a supported library caller invokes a public tool function under a valid security context
- **THEN** the operation result includes dispatcher request/action correlation and the context tracker contains the invocation summary

#### Scenario: Direct API without context has no side effect
- **WHEN** a public filesystem mutation or shell tool is invoked without a valid security context
- **THEN** it returns a structured context denial and creates no file, subprocess, session record, or audit file

#### Scenario: Crew and direct APIs agree on denial
- **WHEN** equivalent policy, confirmation, workspace, and limit contexts receive the same tool action through a Crew adapter and a direct public function
- **THEN** both results have the same decision and stable denial reason

### Requirement: Raw tool operations are internal security-aware helpers
Raw filesystem and shell operation helpers SHALL be private implementation details, SHALL NOT be exported from the product tool package, and SHALL require the active validated security-context snapshot when they perform a security-sensitive operation. Public callers SHALL use dispatcher-backed APIs. Private helpers are not a separate supported authorization entry point.

#### Scenario: Product package exports no raw executor
- **WHEN** a caller inspects the supported exports of the product tool package
- **THEN** only dispatcher-backed tool functions, result types, and supported tracking types are exposed, with no raw execution function

#### Scenario: Private helper still uses context security state
- **WHEN** dispatcher invokes a private filesystem or shell helper
- **THEN** workspace, project policy, classification, and confirmation checks as applicable use the same validated context snapshot

### Requirement: Composite tools are one dispatched action
A composite product tool such as `run_tests` SHALL consume one tool-call allowance and produce one tracker/session result for its top-level invocation. Its internal argument validation, policy/classification/confirmation checks, and subprocess execution SHALL remain within that action and SHALL NOT recursively invoke a public tool API or create duplicate top-level authorization/audit decisions.

#### Scenario: run_tests consumes one call
- **WHEN** `run_tests` validates arguments, obtains authorization, and runs pytest
- **THEN** the tracker gains exactly one `run_tests` summary with one action identifier

#### Scenario: run_tests denial is not duplicated
- **WHEN** `run_tests` is denied before process creation
- **THEN** middleware emits one top-level attempt/result pair for `run_tests` and no nested `run_command` action

## MODIFIED Requirements

### Requirement: CrewAI tool wrappers for Execution Crew
The system SHALL expose CrewAI-compatible tools for `read_file`, `write_file`, `list_dir`, `delete_file`, `run_command`, and `run_tests`. Each wrapper SHALL only adapt CrewAI typed inputs to the corresponding public dispatcher-backed function and format its `ToolResult` for the agent. Wrappers SHALL NOT own tracker limits, session persistence, policy/confirmation decisions, or audit recording.

#### Scenario: Execution agent invokes read_file
- **WHEN** the Execution Crew agent calls the read_file adapter with a valid active security context and workspace path
- **THEN** the public dispatcher-backed `read_file` function runs and middleware records the invocation in the context tracker

#### Scenario: Tracker limit stops further tools
- **WHEN** the active security context tracker has reached `max_tool_calls`
- **THEN** a subsequent Crew adapter call returns the middleware limit-reached failure without executing the underlying operation

#### Scenario: Wrapper has no independent evidence decisions
- **WHEN** a CrewAI adapter receives a tool result
- **THEN** it only formats that result and does not separately append tracker, session, or audit records
