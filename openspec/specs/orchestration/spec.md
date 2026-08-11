# Orchestration

## Purpose

Pipeline coordination for tool call tracking, limits, session persistence, confirmation policy installation, audit logger installation, and passing structured execution summaries to Verification. Introduced in v0.4 alongside `run_tests`; v0.5 adds automatic tracker mounting and optional sandbox sessions; v0.7 installs confirmation policy for the run; v0.8 installs audit logging for sandboxed runs.

## Requirements

### Requirement: Tool call tracking with max_tool_calls limit

The system SHALL provide a `ToolCallTracker` that records tool invocations and enforces a configurable `max_tool_calls` limit. When the limit is reached, subsequent `record()` calls SHALL NOT execute tools and SHALL indicate limit reached.

#### Scenario: Record within limit

- **WHEN** fewer than `max_tool_calls` tools have been recorded
- **THEN** `record()` returns a `ToolCallSummary` for the invocation

#### Scenario: Limit exceeded

- **WHEN** `max_tool_calls` invocations have already been recorded
- **THEN** `record()` returns None and the tracker reports limit reached

### Requirement: Verification receives tool execution summaries

The verification crew SHALL receive structured tool execution summaries including test results (exit code, passed/failed/skipped counts) when available. The verification prompt SHALL instruct the verifier to compare test exit codes and counts against plan success criteria.

#### Scenario: Verification with passing test summary

- **WHEN** tool summaries include a successful `run_tests` result with exit code 0
- **THEN** the verification prompt includes those counts and instructs PASS consideration when criteria match

#### Scenario: Verification with failing test summary

- **WHEN** tool summaries include a failed `run_tests` result with non-zero exit code
- **THEN** the verification prompt includes failure details for FAIL consideration

### Requirement: max_tool_calls configuration

The system SHALL support `max_tool_calls` via environment variable `COUNCIL_MAX_TOOL_CALLS` (default 50). Presets MAY override this value.

#### Scenario: Default limit

- **WHEN** `COUNCIL_MAX_TOOL_CALLS` is not set
- **THEN** `max_tool_calls` defaults to 50

#### Scenario: Preset override

- **WHEN** a preset defines `max_tool_calls`
- **THEN** that value is used instead of the global default

### Requirement: Orchestrator creates session per run

When sandbox is initialized, the orchestrator SHALL create a session before execution and finalize session metadata after the run completes (success or failure).

#### Scenario: Run with sandbox creates session

- **WHEN** `council run` executes with `.council/` present
- **THEN** a new session directory is created and referenced for the duration of the run

#### Scenario: Run without sandbox skips session files

- **WHEN** `council run` executes without `.council/`
- **THEN** the pipeline runs without writing session files (backward compatible)

### Requirement: Execution phase populates tool summaries automatically

During execution, the orchestrator SHALL attach a `ToolCallTracker` to Execution Crew tools so that `ExecutionResult.tool_summaries` is populated automatically without manual injection.

#### Scenario: Summaries after execution

- **WHEN** the Execution Crew completes after invoking tools
- **THEN** `ExecutionResult.tool_summaries` contains one entry per recorded tool call

### Requirement: Orchestrator installs confirmation policy for the run

`run_council` SHALL accept a confirmation mode (and optional confirm function for `ask`) and SHALL install that confirmation policy for the duration of the pipeline, including escalation when it runs. The policy SHALL be reset when the run completes or fails.

#### Scenario: Policy active during execution

- **WHEN** `run_council` is invoked with confirmation mode `auto`
- **THEN** tool calls during execution observe `auto` confirmation behavior

#### Scenario: Policy reset after run

- **WHEN** `run_council` completes (success or failure)
- **THEN** the confirmation policy returns to the prior/default context value

### Requirement: CLI passes resolved confirmation mode to orchestrator

The `council run` command SHALL resolve the confirmation mode from `--yes` and TTY detection and SHALL pass that mode into `run_council` without calling tool modules directly from the CLI.

#### Scenario: council run forwards --yes

- **WHEN** the user invokes `council run` with `--yes`
- **THEN** `run_council` receives confirmation mode `auto`

### Requirement: Install audit logger for sandboxed runs

When `run_council` runs against a project with an initialized sandbox, it SHALL install an audit logger scoped to that run (including the session id when a session is created). The logger SHALL be reset when the run ends, including on failure paths.

#### Scenario: Sandboxed run installs audit logger

- **WHEN** `run_council` starts with an initialized sandbox and creates a session
- **THEN** an audit logger is installed for the duration of the run with that session id available to audit records

#### Scenario: Audit logger reset after run

- **WHEN** `run_council` completes or fails
- **THEN** the audit logger context is reset so subsequent code does not keep writing to that run's logger

#### Scenario: No sandbox skips audit install

- **WHEN** `run_council` runs without an initialized sandbox
- **THEN** no audit logger is installed and the run still proceeds without requiring audit storage

### Requirement: run_council installs project policy for the pipeline

`run_council` SHALL attempt to load `council.policy.yaml` from the resolved workspace/project root and install it as the active policy for the duration of the pipeline. When the file is missing, the run SHALL proceed with no installed policy (built-in defaults). When the file exists but fails validation, the run SHALL fail fast with a clear error before executing crews. The active policy SHALL be reset after the run completes (including on failure).

#### Scenario: Valid policy installed for run

- **WHEN** `run_council` starts and a valid `council.policy.yaml` exists at the project root
- **THEN** the policy is active for tool and path evaluation during that run

#### Scenario: Missing policy file does not fail the run

- **WHEN** `run_council` starts and no `council.policy.yaml` exists
- **THEN** the pipeline continues using built-in defaults

#### Scenario: Invalid policy fails before crews

- **WHEN** `run_council` starts and `council.policy.yaml` fails validation
- **THEN** the run aborts with a validation error and crews are not executed

#### Scenario: Policy reset after run

- **WHEN** a `run_council` invocation finishes (success or failure) after installing a policy
- **THEN** the active policy context is reset so later callers do not inherit that policy
