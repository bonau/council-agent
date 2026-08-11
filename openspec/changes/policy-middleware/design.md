## Context

See `proposal.md` for motivation. The v0.9.1 shell path now derives one canonical argv and fails closed, but product tool concerns are still split:

- filesystem functions own guard and mutate-confirmation checks;
- shell functions own guard, classification, policy, confirmation, and subprocess execution;
- CrewAI `_invoke` owns limits, tracker calls, session writes, and audit writes;
- the orchestrator independently installs project-policy, confirmation, and audit ContextVars.

Direct library calls therefore execute a different evidence path from Crew calls. The change must consolidate the product path without importing CrewAI from `tools/`, changing the project-policy trust model, adding Trust Tier semantics, or weakening v0.9.1 containment.

## Goals / Non-Goals

**Goals:**

- Make `security.middleware.invoke()` the only supported product dispatcher for all six tools.
- Represent one run's workspace, project-policy snapshot, confirmation, limit tracker, request/session identity, optional session writer, and optional audit logger in one immutable `SecurityContext`.
- Make context installation one lexical lifecycle whose closed lease also rejects stale copied contexts.
- Preserve explicit tool-specific security gates while moving all cross-cutting tracking/session/audit ownership into middleware.
- Correlate attempt/result audit records and tracker summaries with stable request/action identifiers, including denials and failures.
- Keep no-sandbox runs functional while making the absence of durable session/audit evidence explicit.

**Non-Goals:**

- Treating project policy as trusted authorization or introducing a versioned policy schema.
- Principal/scopes, session authentication, grants, Trust Tier decisions, or authorization matrices.
- Audit redaction, sequence validation, hash chains, immutable storage, or control-plane protection.
- Expanding the accepted shell grammar or claiming OS/network/process sandboxing.
- Preventing a hostile in-process Python caller from introspecting private implementation objects; the supported product API boundary, not Python module secrecy, is the enforcement contract.

## Decisions

### 1. One immutable context plus a close-on-exit lease

`SecurityContext` is a frozen dataclass containing:

- `request_id` and optional `session_id`;
- a `WorkspaceGuard` rooted at the resolved workspace and constructed with the context's policy denied-path snapshot;
- `CouncilPolicy | None` plus `policy_version="v0.9-unversioned"` (a label, not a new file-schema version);
- one `ConfirmationPolicy`;
- one `ToolCallTracker`;
- optional `SessionManager` and `AuditLogger`;
- a private lifecycle lease shared by derived compatibility views.

`security_context(context)` is the product installation API. It validates non-empty identity, workspace/session agreement, session/audit agreement, and a new lease; installs one ContextVar; marks the lease closed in `finally`; and resets the token. `invoke()` rejects missing, closed, stale, or invalid contexts before registry lookup or execution.

The lease matters because `ContextVar` values can be copied into another async context: resetting the owner's token alone does not invalidate the copied value. Closing a shared lease makes such a copied context fail closed.

Alternatives considered:

- **Independent policy/confirmation/audit ContextVars**: rejected because they permit mixed snapshots and cleanup omissions.
- **A default compat context in each public tool**: rejected because missing product setup would fail open.
- **Passing context as an optional public tool argument**: rejected because callers could accidentally mix ambient and explicit state; public tools always use the one active context.

Legacy policy/confirmation/audit context helpers remain low-level compatibility utilities. When used while a `SecurityContext` is active, they temporarily derive one replacement context view rather than making product tools consult independent ambient state. Orchestrator product code does not use those independent setters.

### 2. Dispatcher registry separates cross-cutting flow from tool-specific decisions

`invoke(tool_name, **args)` owns this fixed sequence:

1. generate an action id and require/validate the active context;
2. validate the registered tool name and typed argument shape;
3. detect tracker limit before calling a tool helper;
4. write an audit `attempt` record when durable audit is available;
5. invoke the registered private helper with the captured context snapshot;
6. normalize expected or unexpected failures to `ToolResult`;
7. attach request/action/decision correlation;
8. record the result once in tracker and optional session;
9. write an audit `result` record, including deny/limit/failure/success.

The registry is closed over the six product tools. Public functions preserve their user-facing signatures but only package typed args and delegate to `invoke()`.

Tool-specific helpers remain in `tools/filesystem.py` and `tools/shell.py` as private context-requiring functions. Filesystem helpers use `context.workspace` and `context.confirmation`; shell helpers use that same guard plus `context.policy` and `context.confirmation`. The raw subprocess helper also requires the active context and an internally prepared canonical action. Private helpers are not exported from `tools.__init__`.

Alternatives considered:

- **Move classification/policy logic entirely into a generic middleware switch**: rejected because typed command and pytest preparation belong with their domain helpers; middleware still owns when and how the single helper result is tracked/audited.
- **Keep tracker in wrappers and only move audit**: rejected because direct API and Crew calls would still enforce different limits and summaries.
- **Call `run_command` from `run_tests`**: rejected because the composite tool would consume two limits and duplicate authorization/audit evidence.

### 3. Audit records gain phase and correlation, not integrity

`AuditRecord` gains backward-compatible optional `phase`, `request_id`, `action_id`, and `decision` fields; attempt records have `success=None`, result records have the actual boolean. The loader supplies defaults for older JSONL lines. Middleware writes directly to the logger captured in `SecurityContext`, not through wrapper-local audit calls.

One accepted action produces two durable records (`attempt`, `result`). A limit denial also produces an attempt/result pair but no tracker summary, because the tracker contract intentionally stores only calls admitted within the maximum. Context-missing denial has no context-owned logger; its returned structured refusal is the only diagnostic evidence.

This does not add sequence numbers, redaction, tamper detection, or a hash chain. Those remain v0.9.4.

### 4. CrewAI wrappers become transport/format adapters

`build_execution_tools()` no longer accepts tracker or session dependencies. Each decorated function calls the corresponding public tool API and formats the returned `ToolResult`. It does not pre-check limits, call `tracker.record`, append session JSONL, or write audit events.

The orchestrator still owns the tracker object so `run_execution()` can copy its summaries into `ExecutionResult`; middleware is the only writer. `build_execution_crew()` only decides whether tools are mounted and does not bind evidence dependencies into wrappers.

### 5. Orchestrator constructs context before building/running product crews

`run_council()` continues to load project policy before crews so malformed policy fails fast. It resolves session/audit objects when sandbox exists, constructs the tracker and `SecurityContext`, and runs planning → execution → verification → escalation inside one `security_context(...)` block. The context is active while crews are built and invoked and is closed before session finalization returns.

With no initialized sandbox:

- `session=None` and `audit_logger=None`;
- middleware still enforces context, workspace, policy, confirmation, and limits;
- successful/failed admitted calls still create in-memory tracker summaries with request/action correlation;
- no `.council/sessions` or `.council/audit` path is created.

## Risks / Trade-offs

- [Direct library calls now require explicit context setup] → document `SecurityContext.create(...)` plus `security_context(...)`; fail with a stable diagnostic instead of silently creating compatibility state.
- [Two audit lines per invocation change event counts] → make phase explicit, keep old JSONL loading backward-compatible, and update CLI/integration assertions to reason by phase/action id.
- [A stale ContextVar may survive token reset in copied async work] → share a close-on-exit lease and validate it on every dispatch/private operation.
- [Legacy context helpers could reintroduce mixed product state] → product dispatcher reads only the captured `SecurityContext`; compatibility helpers derive one complete context view and are not used by orchestrator.
- [Unexpected helper exceptions could otherwise lose evidence] → middleware catches them, returns a structured `tool_exception` failure, and records correlated result evidence.
- [Private Python helpers are introspectable] → require a valid active context in security-sensitive helpers, do not export them, test all supported public paths, and avoid claiming in-process attacker isolation.
- [Audit logger failure could alter tool behavior] → keep current synchronous fail-closed product behavior and expose the failure; integrity/recovery policy is deferred to v0.9.4 rather than silently dropping evidence.

## Migration Plan

1. Add context/lifecycle/dispatcher data flow and focused unit tests without changing Crew mounting.
2. Convert public filesystem and shell functions to dispatcher-backed adapters; retain private context-requiring helpers and run the full regression suite.
3. Install one context in the orchestrator and make legacy security getters reflect it for read-only compatibility.
4. remove tracker/session/audit ownership from Crew wrappers and update integration/e2e tests.
5. Update docs/specs, sync deltas, validate, archive, and run `./scripts/check.sh`.

Rollback is an ordinary revert of this feature's commits before v0.9.2 release. No persisted policy migration or package-version change occurs on this branch; new audit fields are additive and older audit lines remain readable.
