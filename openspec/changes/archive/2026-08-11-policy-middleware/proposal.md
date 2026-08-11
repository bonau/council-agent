## Why

Product tool calls currently cross different combinations of filesystem guards, shell policy/classification, confirmation, tracking, session logging, and audit depending on whether the caller is a CrewAI wrapper or a direct library caller. v0.9.2 closes SEC-P0-002/V1-003 by making one policy middleware dispatcher and one request-scoped `SecurityContext` the mandatory product path before later trust work can build on a reliable choke point.

## What Changes

- Add one tool dispatcher that validates a single `SecurityContext` snapshot, enforces call limits, invokes the tool's security decision and operation, and correlates tracker/session/audit evidence.
- Add lifecycle-scoped `SecurityContext` installation and cleanup with request/session correlation, workspace, policy snapshot identity, confirmation policy, tracker, optional session, and optional audit logger.
- **BREAKING**: Public filesystem and shell tool functions fail closed when no valid `SecurityContext` is installed; raw implementation helpers are private and are not product authorization entry points.
- Move tracking, session persistence, and audit decisions out of CrewAI wrappers; wrappers become formatting/transport adapters over the public dispatcher-backed tool API.
- Record middleware-owned audit attempt/result evidence for successful, failed, policy-denied, and limit-denied calls when sandbox audit storage is available. Without an initialized sandbox, calls still receive correlated results and tracker summaries but no durable audit file is created.
- Add bypass, decision-consistency, missing/stale-context, cleanup, deny/limit audit, and Crew/orchestrator integration tests.
- Update public and release-handoff documentation to state the new product boundary and remaining security limitations.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Define the mandatory dispatcher, `SecurityContext` snapshot/lifecycle, fail-closed context behavior, correlated middleware audit, and no-sandbox behavior.
- `tools`: Require every public filesystem/shell tool API and CrewAI adapter invocation to use the dispatcher without a second executable product path.
- `orchestration`: Install and clean up one `SecurityContext` for the full run and delegate tracking/session/audit ownership to middleware.

## Non-goals

- Trust Tier 0/1/2 runtime, trust grants, or `council trust` behavior.
- A versioned project-policy schema or project-policy trust-boundary changes (v0.9.3).
- Audit hash chains, sequence/integrity verification, control-plane hardening, or secret redaction (v0.9.4).
- Principal/API-key scope or authorization identity semantics (v0.9.5).
- Session authentication or step-up authentication.
- Additional shell containment or general-purpose shell grammar beyond the v0.9.1 boundary.

## Impact

- Runtime: `src/council_agent/security/middleware.py`, tool filesystem/shell entry points, confirmation/policy/audit compatibility accessors, tracker/session integration, Execution Crew adapters, and orchestrator context lifecycle.
- API: direct product library callers must create and install a `SecurityContext`; Crew wrappers no longer accept tracker/session responsibility.
- Tests/specs: security, tools, and orchestration requirements and their unit/integration/e2e coverage change.
- Dependencies: no new runtime dependency and no package-version bump on this feature branch.
