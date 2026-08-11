## Context

See `proposal.md` for motivation. v0.9.5 already separates provider credentials from Council principals and reevaluates scopes per dispatcher action, but a session UUID and `ConfirmMode.AUTO` still provide no authenticated-user evidence. The existing v0.9.4 audit substrate can persist sanitized administrative result events in addition to correlated tool attempt/result pairs.

This change must remain process-local: a user-owned persistent authorization store belongs to v0.9.7, and the complete Trust Tier decision matrix belongs to v0.9.8.

## Goals / Non-Goals

**Goals:**

- Introduce one-use challenge and step-up proof state independent from session persistence.
- Bind every proof to the current principal, canonical workspace, runtime session, purpose, and exact top-level action.
- Require a fresh proof for actions whose existing scope requirement contains `high-risk:manage`.
- Support non-interactive test/service authentication through a typed secret verifier while keeping confirmation behavior independent.
- Emit useful lifecycle and dispatcher evidence containing only hashes/masked references.

**Non-Goals:**

- Persistent verifier, grant, or revocation storage.
- Interactive login UX, remote identity, Trust Tier runtime, or a general policy decision matrix.
- Protecting verifier bytes in process memory from a hostile in-process caller.

## Decisions

### Process-local authentication manager with fail-closed restart semantics

An `AuthenticationManager` owns outstanding challenge digests, one-use step-up token digests, replay tombstones, expiry, and revocation state. It is a separate object referenced by `SecurityContext`; the session UUID is only one field in each proof binding.

All state is intentionally memory-only. A process restart invalidates every outstanding challenge and step-up token because a new manager has no matching digest. A configured verifier may authenticate again after restart. This gives safe failure behavior without prematurely creating the user-owned persistent store assigned to v0.9.7.

Alternative considered: persist authentication under `.council/auth/`. Rejected because workspace-local state is writable by the project threat boundary and would overlap the v0.9.7 grant-store work.

### HMAC challenge response and opaque one-use step-up token

The manager derives an in-memory verifier key from a typed secret. It issues a random challenge ID and nonce bound to:

- masked principal reference,
- hash of the canonical workspace,
- runtime session ID,
- purpose (`high-risk-action`),
- hash of the canonical top-level tool name and arguments,
- issue and expiry times.

A response is an HMAC over the full challenge envelope. Completing a challenge consumes it before credential comparison and returns a random opaque step-up token only on success. Consuming a step-up token also consumes it before binding checks. Digests and bounded tombstones remain in memory so repeated challenges or tokens produce an explicit replay result.

Alternative considered: use the session ID or a bearer token directly. Rejected because neither proves the exact principal/workspace/action binding and reusable bearer tokens violate the replay requirement.

### Product context opts into the high-risk step-up boundary

The security context has an explicit `require_high_risk_step_up` invariant. The product orchestrator always enables it; direct library contexts default to disabled for compatibility and can explicitly enable it. When enabled, the dispatcher requires fresh step-up exactly when the canonical action's existing cumulative scope set includes `high-risk:manage`. This currently covers dangerous shell actions and reuses the v0.9.5 action model without introducing Trust Tier behavior. The freshness limit is stricter than the token's absolute expiry; either limit can reject the proof.

Scope authorization runs first. A caller lacking high-risk scope is denied without attempting authentication. For a scoped high-risk caller, authentication runs before project confirmation and the tool handler. Therefore `--yes` can only choose automatic confirmation after authentication has succeeded.

Alternative considered: unconditionally enable the new gate for every low-level context or let callers opt arbitrary actions into a tier. Unconditional enablement would break supported library callers that have not migrated to authentication; arbitrary tier selection belongs to the v0.9.8/v1.0 decision matrix. Product paths enable the bounded high-risk rule now, while library callers receive an explicit migration seam.

### Provider callback mints an action-bound proof

`SecurityContext` holds the authentication manager and an optional step-up provider. A provider receives the exact runtime binding and returns an opaque token. The CLI/service provider uses a typed environment verifier to issue and answer a fresh challenge for each high-risk action. Tests and library integrations can inject providers that return missing, stale, replayed, revoked, or mismatched tokens.

No command-line secret option is added; command-line arguments are observable through process listings. `COUNCIL_AUTH_SECRET` is loaded as `SecretStr`, passed separately from both the provider credential and Council principal, and never displayed. An absent verifier leaves ordinary scoped actions compatible but makes high-risk actions fail closed even with `--yes`.

### Authentication lifecycle events are sanitized administrative audit records

The manager emits standalone `session_auth` result events for success, failure, expiry, revocation, replay, and binding mismatch when an audit sink exists. Events include only stable reason codes and masked references for principal, workspace, action, challenge, and token. Tool attempt/result metadata additionally includes the normalized authentication decision.

Raw verifier values, challenge IDs/nonces, responses, and step-up tokens are never passed to the audit/session writers. Existing recursive redaction remains defense in depth.

## Risks / Trade-offs

- [A configured service verifier can mint multiple fresh proofs during one process] → Each proof remains exact-action-bound and one-use; operator-controlled verifier rotation/restart is documented, while persistent revocation remains v0.9.7.
- [In-memory replay tombstones are lost on restart] → Outstanding tokens are also lost and therefore fail closed; a raw old token cannot be consumed by a new manager.
- [Clock rollback could extend apparent freshness] → Require timezone-aware UTC timestamps and reject negative age or expiry inconsistencies.
- [Hash references can correlate repeated identities/actions] → Use SHA-256 references without raw values; this correlation is required for audit usefulness.
- [Authentication before confirmation may consume a token for an action later refused] → The service provider mints per attempt, and consuming before lower gates prevents proof reuse against a changed decision.

## Migration Plan

1. Add the pure authentication model and lifecycle tests.
2. Add dispatcher binding/step-up enforcement and no-side-effect bypass tests.
3. Wire optional verifier input through settings, CLI, and orchestrator, then run full regression.
4. Existing product runs without high-risk actions need no new configuration. Product high-risk CLI/service runs must set `COUNCIL_AUTH_SECRET`; `--yes` alone now fails closed. Direct library contexts can opt into the same high-risk requirement explicitly.
5. Rollback removes the optional authentication fields and high-risk gate; no persistent authentication data requires migration.
