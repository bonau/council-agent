## ADDED Requirements

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
