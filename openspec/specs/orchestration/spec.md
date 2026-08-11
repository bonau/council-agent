# Orchestration

## Purpose

Pipeline coordination for tool call tracking, limits, session persistence, confirmation policy installation, audit logger installation, and passing structured execution summaries to Verification. Introduced in v0.4 alongside `run_tests`; v0.5 adds automatic tracker mounting and optional sandbox sessions; v0.7 installs confirmation policy for the run; v0.8 installs audit logging for sandboxed runs.

## Requirements

### Requirement: Orchestrator owns one security context lifecycle

Before a product pipeline can invoke tools, the orchestrator SHALL require a Council principal separately from the OpenRouter provider credential and SHALL construct and install one validated security context containing the resolved workspace, loaded project-policy snapshot, resolved confirmation policy, per-run tracker, request/session correlation, expected principal identity/current-authority source, optional sandbox session writer, and optional sandbox audit logger. The same context SHALL remain active through execution and escalation, current principal authority SHALL be resolved for each action, and the context SHALL be cleaned up on every success or failure path.

#### Scenario: One context spans execution and escalation

- **WHEN** a run reaches execution and subsequently escalation
- **THEN** all product tool invocations in both phases observe the same request, workspace, policy snapshot, confirmation policy, tracker, session, audit correlation, and expected principal identity

#### Scenario: Run failure cleans context

- **WHEN** planning, execution, verification, or escalation raises an exception
- **THEN** the orchestrator closes and resets the installed security context before returning or re-raising

#### Scenario: Later run cannot inherit prior context

- **WHEN** one run completes and another caller invokes a public tool outside a newly installed run context
- **THEN** the tool fails closed rather than inheriting principal, policy, confirmation, tracker, session, or audit state from the completed run

#### Scenario: Missing principal fails before crews

- **WHEN** a library run omits its Council principal
- **THEN** the run fails closed before constructing crews and does not treat the provider credential or session identifier as a principal

### Requirement: Provider credential and Council principal use separate data flows

The CLI and orchestration API SHALL load and pass the OpenRouter API key as a typed provider credential used only to construct model clients. They SHALL independently resolve and pass a Council principal used only for tool authorization. Supplying one SHALL NOT synthesize, validate, or expand the other, and diagnostic output SHALL NOT echo raw credential or principal identifier values.

#### Scenario: Model builders receive provider credential only

- **WHEN** the orchestrator constructs planning, execution, verification, or escalation model clients
- **THEN** each builder receives the typed OpenRouter provider credential and no Council scope data

#### Scenario: Security context receives principal only

- **WHEN** the orchestrator constructs the run security context
- **THEN** it receives the Council principal/current-authority source and no OpenRouter API key

#### Scenario: Provider credential is not accepted as principal

- **WHEN** a caller passes a provider credential in the Council-principal position
- **THEN** orchestration fails before the pipeline and no tool authority is installed

### Requirement: CLI principal configuration is strict and independent

The CLI SHALL resolve a stable local Council principal identifier, recognized kind/issuer, and explicit scope set independently of `OPENROUTER_API_KEY`. It SHALL provide a full recognized local scope set by default for compatibility, SHALL allow the scope set to be narrowed through Council-specific configuration, and SHALL fail before the pipeline on unknown scope names. This local declaration SHALL NOT be represented as session authentication or a persistent trust grant.

#### Scenario: Default local CLI principal preserves supported tool access

- **WHEN** no Council-specific scope override is configured
- **THEN** the CLI constructs a stable local principal with the full recognized scope set while keeping the OpenRouter key separate

#### Scenario: Read-only CLI principal is narrowed

- **WHEN** Council-specific scope configuration contains only `read`
- **THEN** the resulting principal can proceed to read-tool gates and is denied for mutation, test, and shell actions

#### Scenario: Unknown configured scope fails fast

- **WHEN** Council-specific scope configuration includes an unrecognized value
- **THEN** the CLI reports a sanitized configuration error and does not start the pipeline

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

### Requirement: CLI passes resolved confirmation mode to orchestrator

The `council run` command SHALL resolve the confirmation mode from `--yes` and TTY detection and SHALL pass that mode into `run_council` without calling tool modules directly from the CLI.

#### Scenario: council run forwards --yes

- **WHEN** the user invokes `council run` with `--yes`
- **THEN** `run_council` receives confirmation mode `auto`

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

### Requirement: run_council installs project policy for the pipeline

`run_council` SHALL attempt to load the resolved project-root `council.policy.yaml` before creating a session, security context, audit writer, or any crew. When the file is missing, the context SHALL contain no project policy, SHALL use built-in defaults, and SHALL carry the built-in policy-version label. When the file exists, the orchestrator SHALL require one complete supported schema-version policy; any malformed YAML, missing or unsupported version, unknown field, misspelled field, or invalid known field SHALL fail fast without installing any policy subset. A valid loaded policy and its schema-version label SHALL be stored in the one context snapshot and removed together when that context is cleaned up.

#### Scenario: Valid policy installed for run

- **WHEN** `run_council` starts and a valid `schema_version: 1` `council.policy.yaml` exists at the resolved project root
- **THEN** the resulting security context snapshot supplies that complete restrict-only policy and its version 1 label to dispatched tool and path evaluation during the run

#### Scenario: Missing policy file does not fail the run

- **WHEN** `run_council` starts and no `council.policy.yaml` exists
- **THEN** the pipeline continues with a valid security context whose project policy is absent, whose evaluators use built-in defaults, and whose policy-version label identifies that built-in state

#### Scenario: Invalid policy fails before crews

- **WHEN** `run_council` starts and `council.policy.yaml` has invalid YAML, schema version, fields, or field types
- **THEN** the run aborts with a sanitized validation error before a session, audit writer, security context, or crew is created

#### Scenario: Unknown field cannot be partially applied

- **WHEN** a policy contains valid denial fields together with an unknown or misspelled field
- **THEN** the orchestrator rejects the whole file and does not start a run using only the recognized denials

#### Scenario: Policy reset after run

- **WHEN** a `run_council` invocation finishes after loading a valid versioned policy
- **THEN** context cleanup prevents later callers from inheriting either that policy snapshot or its schema-version label

### Requirement: Orchestrator installs independent authentication state

The orchestrator SHALL create a non-empty runtime session identifier for every run, SHALL enable the security context's high-risk step-up requirement, and SHALL install optional process-local authentication state in the same security-context lifecycle while keeping it distinct from the Council principal, provider credential, project policy, confirmation policy, and persisted session writer. Cleanup SHALL revoke and remove the run's outstanding authentication state on success and failure.

#### Scenario: Sandboxed run binds authentication to persisted session

- **WHEN** a sandboxed run configures a service verifier
- **THEN** authentication binds to the same session identifier used for audit/session correlation without storing authentication credentials in that session

#### Scenario: Non-sandbox run has runtime session binding

- **WHEN** a run has no initialized sandbox
- **THEN** it still has a process-local runtime session identifier for authentication binding while writing no session files

#### Scenario: Cleanup invalidates outstanding state

- **WHEN** a run completes or raises after creating authentication challenges or tokens
- **THEN** its authentication manager is revoked and a later run cannot consume those outstanding values

### Requirement: CLI service authentication is typed and non-interactive

The CLI SHALL optionally load a Council authentication verifier from a dedicated secret setting independent of `OPENROUTER_API_KEY`, principal configuration, and command-line arguments. When configured, the orchestrator SHALL use it to produce a new exact-action challenge response and one-use step-up token for each high-risk action. The CLI SHALL display only whether step-up authentication is configured and SHALL NOT display the verifier or generated proof values.

#### Scenario: Configured verifier supports automated step-up

- **WHEN** a non-interactive run has a valid dedicated authentication verifier and requests a scoped high-risk action
- **THEN** the action receives fresh exact-action step-up evidence and proceeds to remaining policy/confirmation gates

#### Scenario: Missing verifier fails closed only where required

- **WHEN** no authentication verifier is configured
- **THEN** ordinary scoped actions remain compatible and high-risk actions are denied for missing authentication

#### Scenario: Authentication input remains separate

- **WHEN** the CLI loads provider credential, principal settings, confirmation flags, and authentication verifier
- **THEN** each value follows its dedicated data flow and none synthesizes or expands another

### Requirement: Confirmation flags never authenticate

`--yes` and confirmation mode SHALL only select confirmation behavior. They SHALL NOT create an authentication manager, answer a challenge, issue or consume a step-up token, satisfy freshness, or override an authentication denial.

#### Scenario: --yes without authentication is denied

- **WHEN** `council run --yes` reaches a scoped high-risk action without a configured verifier or matching fresh proof
- **THEN** the action is denied before confirmation and no filesystem or subprocess side effect occurs

#### Scenario: Authentication does not bypass confirmation policy

- **WHEN** a high-risk action has valid fresh authentication but confirmation mode refuses or project policy denies it
- **THEN** the action remains denied by that later gate
