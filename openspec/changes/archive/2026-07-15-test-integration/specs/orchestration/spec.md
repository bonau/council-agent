## ADDED Requirements

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
