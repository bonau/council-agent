## ADDED Requirements

### Requirement: One mandatory policy dispatcher for product tool calls
Every product invocation of a filesystem or shell tool SHALL enter one dispatcher before any tool operation is performed. The dispatcher SHALL use one action identity to validate context, enforce the tool-call limit, obtain the tool-specific security decision, track the result, persist optional session evidence, emit optional durable audit evidence, and return the result. CLI, CrewAI, escalation, and supported library product paths SHALL NOT expose a second executable tool path.

#### Scenario: Same action has one product decision path
- **WHEN** the same canonical tool name and arguments are invoked through a supported library entry point and through a CrewAI adapter under equivalent contexts
- **THEN** both invocations pass through the dispatcher and produce equivalent allow or deny decisions and reason metadata

#### Scenario: Direct public tool call cannot bypass dispatcher
- **WHEN** a caller imports a public filesystem or shell tool function directly
- **THEN** the function delegates to the dispatcher rather than executing a raw operation

#### Scenario: Unknown tool is denied
- **WHEN** the dispatcher receives a tool name outside the registered product tool set
- **THEN** it returns a structured denial and performs no filesystem operation or subprocess execution

### Requirement: Security context is one validated snapshot
Each dispatched action SHALL use exactly one immutable security-context snapshot containing a non-empty request identifier, optional session identifier, workspace guard/root, project-policy snapshot and policy-version label, confirmation policy, tool-call tracker, optional session writer, and optional audit logger. Context validation SHALL reject inconsistent workspace/session or session/audit identities before the tool-specific operation runs. Reserved fields for future authorization work SHALL NOT grant principal, authentication, grant, or Trust Tier semantics in this milestone.

#### Scenario: Valid context supplies one action snapshot
- **WHEN** a valid context is active and a tool is invoked
- **THEN** workspace, project policy, confirmation behavior, request/session correlation, and call limit for that invocation all come from that same context object

#### Scenario: Context identity mismatch fails closed
- **WHEN** a context's session workspace or audit session identity does not match the context workspace/session
- **THEN** context installation or invocation is rejected before a tool operation starts

#### Scenario: Policy label does not create a versioned schema
- **WHEN** a context represents the current unversioned v0.9 project policy
- **THEN** it carries an explicit unversioned policy label without accepting or claiming a versioned policy-file schema

### Requirement: Security context lifecycle fails closed
A product scope SHALL install and clean up its security context through one lifecycle operation. A missing context, a context that was already closed, or a stale context retained after cleanup SHALL be denied with a structured diagnostic result. No default product context SHALL be synthesized by a public tool function.

#### Scenario: Missing context is denied
- **WHEN** a public product tool is called without an installed security context
- **THEN** it returns `success=False` with a stable `security_context_missing` rejection reason and performs no operation

#### Scenario: Cleanup prevents later use
- **WHEN** a product scope exits and cleans up its security context
- **THEN** a later tool call in that scope fails closed instead of retaining policy, confirmation, tracker, session, or audit state

#### Scenario: Stale copied context is denied
- **WHEN** an execution context copied while a security context was active attempts a tool call after the owning lifecycle has closed
- **THEN** the call is rejected as a closed security context and performs no operation

### Requirement: Middleware evidence correlates attempts and results
When durable audit storage is present in the security context, the dispatcher SHALL emit an attempt record before an accepted tool operation and a result record after completion or refusal. Both records SHALL carry the same request and action identifiers, tool name, and session identifier when present. Policy denial, confirmation denial, tool-limit denial, expected tool failure, unexpected execution failure, and success SHALL all produce correlated result evidence. This correlation is not an audit hash chain or integrity guarantee.

#### Scenario: Successful action has correlated audit phases
- **WHEN** a dispatched tool succeeds with durable audit storage configured
- **THEN** its attempt and result audit records share one request/action correlation and the result records an allow decision

#### Scenario: Policy denial is audited by middleware
- **WHEN** a shell action is denied by project policy with durable audit storage configured
- **THEN** middleware records a correlated denied result and no subprocess starts

#### Scenario: Tool limit denial is audited by middleware
- **WHEN** a tool call is attempted after the context tracker reaches its limit
- **THEN** middleware records the limit-denied attempt/result correlation and does not invoke the tool operation

#### Scenario: No sandbox has no durable audit file
- **WHEN** a product run has no initialized sandbox and therefore its context has no audit logger or session writer
- **THEN** the dispatcher still returns request/action/decision metadata and records allowed calls in the in-memory tracker, but creates no durable audit or session file

## MODIFIED Requirements

### Requirement: Structured audit log records
The system SHALL support appending structured audit records for dispatched tool invocations. Each middleware-owned record SHALL include: a UTC timestamp, phase (`attempt` or `result`), tool name, arguments, optional success boolean, optional error message, metadata (JSON-serializable), request id, action id, decision when known, and optional session id identifying the caller run. Existing non-tool administrative audit callers MAY emit a single `result` record. When no audit logger is installed for the current security context, durable recording SHALL be a no-op.

#### Scenario: Record includes required fields
- **WHEN** an audit logger is installed and a dispatched tool invocation completes or is denied
- **THEN** the appended result record includes timestamp, phase, tool name, arguments, success, request id, action id, decision, and session id when available

#### Scenario: Attempt and result correlate
- **WHEN** middleware records both phases of one invocation
- **THEN** the records have the same request id, action id, tool, arguments, and optional session id

#### Scenario: No logger is a no-op
- **WHEN** no audit logger is present in the active security context
- **THEN** no audit file is written and no audit-storage error is raised

### Requirement: Context-scoped active policy
The project policy used by product tool and guard evaluation SHALL be the policy snapshot stored in the active security context. A valid context whose policy value is absent SHALL apply built-in defaults (no extra command denials/allowlist and no extra denied paths from project policy). Installing and resetting the security context SHALL install and reset that policy snapshot together with the workspace, confirmation, tracker, session, and audit state.

#### Scenario: No installed policy uses built-in defaults
- **WHEN** an active valid security context contains no project policy
- **THEN** command policy checks impose no extra deny/allow list beyond built-in classifier and confirmation behavior

#### Scenario: Installed policy is visible to evaluators
- **WHEN** a valid context contains a loaded project policy
- **THEN** command and path evaluations for each dispatched action use that snapshot until the context is cleaned up

#### Scenario: Missing context does not use policy defaults
- **WHEN** no security context is installed
- **THEN** public tool invocation is denied rather than proceeding with an ambient default policy
