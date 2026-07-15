# Orchestration

## Purpose

Pipeline coordination for tool call tracking, limits, session persistence, and passing structured execution summaries to Verification. Introduced in v0.4 alongside `run_tests`; v0.5 adds automatic tracker mounting and optional sandbox sessions.

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
