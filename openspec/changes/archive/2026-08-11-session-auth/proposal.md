## Why

A session UUID currently correlates records but proves no authenticated user presence. Before Trust Tier decisions can safely require elevated authority, Council needs a replay-resistant session authentication foundation that binds fresh step-up evidence to the current principal, workspace, session, purpose, and lifetime without exposing credentials.

## What Changes

- Add authentication challenges and one-use step-up tokens whose state is independent from session identifiers.
- Bind challenges and tokens to a masked principal identity, canonical workspace, session, purpose, issue time, expiry, and freshness window.
- Make high-privilege dispatcher decisions fail closed when authentication is missing, expired, revoked, replayed, or bound to different context.
- Provide an explicit non-interactive service/test verifier path that is revocable and remains separate from `--yes`.
- Emit correlated, masked audit evidence for authentication success, failure, expiry, revocation, and replay while keeping challenge secrets, verifier material, and raw tokens out of audit, session, console, and release evidence.
- Define restart behavior: authentication state is process-local and fails closed after restart.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Define authentication lifecycle, context binding, fresh step-up enforcement, replay/revoke behavior, and masked decision evidence.
- `sandbox`: Separate session record identity from authentication state and prohibit authentication credentials in session persistence.
- `orchestration`: Install optional authentication state independently of confirmation mode and ensure `--yes` cannot authenticate or satisfy step-up.

## Impact

- Affects `src/council_agent/security/`, the dispatcher `SecurityContext`, `src/council_agent/sandbox/session.py`, orchestrator/CLI authentication input boundaries, and their tests.
- Adds no remote identity provider or persistent trust-grant dependency.
- High-privilege actions can now opt into mandatory fresh step-up; existing non-high-privilege scope behavior remains compatible.

## Non-goals

- Trust Tier 0/1/2 runtime or a trust decision matrix.
- A persistent user-owned trust grant store.
- Remote SSO, OAuth, WebAuthn, or multi-user server authentication.
- Package version bump, release tag, or release-branch work.
- Protection from a hostile in-process Python caller, host owner/root, or an OS-level attacker.
