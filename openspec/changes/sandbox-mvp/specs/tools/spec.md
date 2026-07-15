## REMOVED Requirements

### Requirement: Tools are not integrated with Execution Crew

## ADDED Requirements

### Requirement: CrewAI tool wrappers for Execution Crew

The system SHALL expose CrewAI-compatible tools for `read_file`, `write_file`, `list_dir`, `delete_file`, `run_command`, and `run_tests`. Each wrapper SHALL invoke the corresponding standalone function and return a string summary suitable for the agent. Wrappers SHALL route invocations through `ToolCallTracker.record()`.

#### Scenario: Execution agent invokes read_file

- **WHEN** the Execution Crew agent calls the read_file tool with a valid workspace path
- **THEN** the underlying `read_file` function runs and the tracker records the invocation

#### Scenario: Tracker limit stops further tools

- **WHEN** `max_tool_calls` has been reached
- **THEN** subsequent tool wrapper calls return a limit-reached message without executing the underlying function
