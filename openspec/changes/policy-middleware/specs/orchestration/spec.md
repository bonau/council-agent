## ADDED Requirements

### Requirement: Orchestrator owns one security context lifecycle
Before a product pipeline can invoke tools, the orchestrator SHALL construct and install one validated security context containing the resolved workspace, loaded project-policy snapshot, resolved confirmation policy, per-run tracker, request/session correlation, optional sandbox session writer, and optional sandbox audit logger. The same context SHALL remain active through execution and escalation and SHALL be cleaned up on every success or failure path.

#### Scenario: One context spans execution and escalation
- **WHEN** a run reaches execution and subsequently escalation
- **THEN** all product tool invocations in both phases observe the same request, workspace, policy snapshot, confirmation policy, tracker, session, and audit correlation

#### Scenario: Run failure cleans context
- **WHEN** planning, execution, verification, or escalation raises an exception
- **THEN** the orchestrator closes and resets the installed security context before returning or re-raising

#### Scenario: Later run cannot inherit prior context
- **WHEN** one run completes and another caller invokes a public tool outside a newly installed run context
- **THEN** the tool fails closed rather than inheriting policy, confirmation, tracker, session, or audit state from the completed run

## MODIFIED Requirements

### Requirement: Execution phase populates tool summaries automatically
During execution, the orchestrator SHALL place a `ToolCallTracker` in the active security context. The policy dispatcher SHALL record each allowed top-level tool invocation result so that `ExecutionResult.tool_summaries` is populated automatically without manual wrapper injection. Calls denied because the tracker is already at its limit SHALL not execute and SHALL be represented by middleware denial evidence.

#### Scenario: Summaries after execution
- **WHEN** the Execution Crew completes after invoking tools
- **THEN** `ExecutionResult.tool_summaries` contains one entry per top-level tool call accepted within the tracker limit

#### Scenario: Wrapper does not add a duplicate summary
- **WHEN** a CrewAI tool adapter formats a dispatcher result
- **THEN** the tracker contains exactly the middleware-created summary for that action

### Requirement: Orchestrator installs confirmation policy for the run
`run_council` SHALL accept a confirmation mode (and optional confirm function for `ask`) and SHALL store that confirmation policy in the single security context for the duration of the pipeline, including escalation when it runs. Context cleanup SHALL remove the confirmation policy together with all other run security state when the run completes or fails.

#### Scenario: Policy active during execution
- **WHEN** `run_council` is invoked with confirmation mode `auto`
- **THEN** dispatched tool calls during execution observe `auto` confirmation behavior from the active security context

#### Scenario: Policy reset after run
- **WHEN** `run_council` completes or fails
- **THEN** no security context remains active and subsequent product tool calls cannot use the run's confirmation policy

### Requirement: Install audit logger for sandboxed runs
When `run_council` runs against a project with an initialized sandbox, it SHALL place an audit logger in the single run security context, correlated to the created session. Middleware SHALL own tool attempt/result audit writes. Context cleanup SHALL remove the logger with the rest of the run state, including on failure paths.

#### Scenario: Sandboxed run installs audit logger
- **WHEN** `run_council` starts with an initialized sandbox and creates a session
- **THEN** the active security context has an audit logger for the duration of the run with the same session id

#### Scenario: Audit logger reset after run
- **WHEN** `run_council` completes or fails
- **THEN** no active security context exposes that run's audit logger

#### Scenario: No sandbox skips audit install
- **WHEN** `run_council` runs without an initialized sandbox
- **THEN** its security context has no session writer or audit logger, the run still proceeds, middleware still tracks in memory, and no audit/session files are created

### Requirement: run_council installs project policy for the pipeline
`run_council` SHALL attempt to load `council.policy.yaml` from the resolved workspace/project root before constructing the security context. When the file is missing, the context SHALL contain no project policy and use built-in defaults. When the file exists but fails validation, the run SHALL fail fast before installing a context or executing crews. A valid loaded policy SHALL be stored in the one context snapshot and removed when that context is cleaned up.

#### Scenario: Valid policy installed for run
- **WHEN** `run_council` starts and a valid `council.policy.yaml` exists at the project root
- **THEN** the resulting security context snapshot supplies that policy to dispatched tool and path evaluation during the run

#### Scenario: Missing policy file does not fail the run
- **WHEN** `run_council` starts and no `council.policy.yaml` exists
- **THEN** the pipeline continues with a valid security context whose project policy is absent and whose evaluators use built-in defaults

#### Scenario: Invalid policy fails before crews
- **WHEN** `run_council` starts and `council.policy.yaml` fails validation
- **THEN** the run aborts with a validation error and no context or crew is started

#### Scenario: Policy reset after run
- **WHEN** a `run_council` invocation finishes after loading a policy
- **THEN** context cleanup prevents later callers from inheriting that policy snapshot
