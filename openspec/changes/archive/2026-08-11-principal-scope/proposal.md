## Why

`OPENROUTER_API_KEY` is a provider credential for model access, but the runtime currently has no separate identity that authorizes Council tool actions. Before session authentication and trust grants can be added, every dispatched action needs a stable principal and an explicit, fail-closed scope decision.

## What Changes

- **BREAKING**: require product/library runs to supply a Council authorization principal separately from the typed OpenRouter provider credential.
- Add an immutable principal model with a stable ID, kind, issuer, and explicit scopes for read, filesystem mutation, tests, shell, and high-risk management.
- Add a per-action scope matrix and enforce it in the mandatory dispatcher before handlers, policy, confirmation, filesystem operations, or subprocess creation.
- Require composite actions to hold every scope needed for their top-level authority; in particular, `run_tests` cannot be used by a read-only principal to execute mutating project code.
- Resolve current principal authority for every action so a missing, invalid, mismatched, tightened, or revoked principal fails closed without using stale scopes.
- Add masked principal references and scope-decision details to middleware results and recursively sanitized audit/session evidence without persisting raw credentials.
- Document the provider/principal data flow, scope matrix, compatibility impact, evidence, and remaining authorization boundaries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Define Council principals and scopes, require fail-closed dispatcher authorization, and record masked scope decisions in audit evidence.
- `tools`: Require each public and composite tool action to satisfy the canonical scope matrix before execution.
- `orchestration`: Construct the run security context from a Council principal that is distinct from the OpenRouter provider credential.

## Non-goals

- Session authentication, challenge/step-up, expiry, or replay protection (v0.9.6).
- A persistent user-owned trust grant/revoke store (v0.9.7).
- Trust Tier runtime behavior or treating `ConfirmMode`/`--yes` as authorization.
- Remote IAM, OAuth, or changes to OpenRouter's provider permission model.
- A release version bump, release tag, or release-branch work.

## Impact

- Affected code: `security/principal.py`, `security/middleware.py`, `security/audit.py`, `orchestrator.py`, OpenRouter/crew credential plumbing, CLI settings, and product tool tests.
- Public API impact: `run_council` and crew builders receive a typed provider credential; `run_council` also requires a Council principal. Direct `SecurityContext` callers must install a principal to execute tools.
- Configuration impact: CLI principal identity/scopes are loaded independently from `OPENROUTER_API_KEY`; unknown scope names fail before the pipeline starts.
- No new dependency, provider permission, authentication protocol, grant store, or version bump is introduced.
