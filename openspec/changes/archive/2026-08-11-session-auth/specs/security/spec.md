## ADDED Requirements

### Requirement: Session authentication state is independently bound

Authentication state SHALL be distinct from a request identifier, session UUID, Council principal declaration, provider credential, project policy, confirmation result, and trust grant. Every authentication challenge and step-up token SHALL be bound to the current masked principal identity, canonical workspace, non-empty runtime session identifier, declared authentication purpose, exact canonical top-level action, issue time, and expiry.

#### Scenario: Session identifier alone does not authenticate

- **WHEN** a high-privilege action has a valid session identifier and principal scope but no valid step-up authentication
- **THEN** the dispatcher denies the action before its handler and does not treat the session identifier as proof

#### Scenario: Wrong binding is denied

- **WHEN** a challenge or step-up token is presented for a different principal, workspace, session, purpose, tool, or arguments
- **THEN** authentication fails closed with a stable binding-mismatch reason and the action does not execute

#### Scenario: Provider credential does not authenticate

- **WHEN** an OpenRouter credential is available but no Council authentication verifier or proof is available
- **THEN** the provider credential is not used as step-up evidence

### Requirement: Challenges and step-up tokens are fresh and non-replayable

Authentication challenges and issued step-up tokens SHALL contain unpredictable values, SHALL have bounded lifetimes, and SHALL be consumable at most once. Challenge completion SHALL consume the challenge before credential comparison. Step-up evaluation SHALL consume the token before binding evaluation. Missing, unknown, expired, revoked, previously consumed, or insufficiently fresh evidence SHALL be denied with stable reason metadata. Restart SHALL invalidate all outstanding process-local challenges and tokens.

#### Scenario: Successful challenge creates one token

- **WHEN** a valid verifier response completes an unexpired challenge with matching binding
- **THEN** authentication succeeds and produces one opaque step-up token without persisting the verifier, response, challenge value, or token value

#### Scenario: Challenge replay is denied

- **WHEN** a completed or failed challenge is submitted again
- **THEN** completion is denied as replay and no additional step-up token is issued

#### Scenario: Token replay is denied

- **WHEN** a step-up token has already been evaluated once
- **THEN** a later evaluation is denied as replay even if the original evaluation was denied for a binding mismatch

#### Scenario: Expired or stale proof is denied

- **WHEN** a challenge or step-up token exceeds its absolute expiry or the high-privilege decision's freshness window
- **THEN** authentication is denied as expired before the action executes

#### Scenario: Revocation applies immediately

- **WHEN** the process-local authentication manager is revoked
- **THEN** outstanding challenges and tokens are rejected and no new challenge is issued by that manager

#### Scenario: Restart invalidates outstanding proof

- **WHEN** an opaque challenge or token from a prior manager instance is presented after process restart
- **THEN** the new manager rejects it as unknown rather than recovering authentication from the session UUID

### Requirement: High-privilege actions require fresh step-up

After principal scope authorization succeeds, a security context that explicitly requires high-risk step-up SHALL require every canonical action needing `high-risk:manage` to present a successful, matching, one-use proof within the configured freshness window before project confirmation or the tool handler. Product orchestration contexts SHALL enable this requirement. Direct library contexts MAY leave it disabled for backward compatibility or explicitly enable it. When required, authentication denial SHALL NOT be overridden by project policy, wrappers, confirmation mode, or `--yes`. Actions not requiring `high-risk:manage` SHALL NOT be elevated or otherwise changed by the presence of authentication state.

#### Scenario: Missing step-up denies high-risk action

- **WHEN** a principal has all scopes for a dangerous shell action, the context requires high-risk step-up, but it has no authentication manager or step-up provider
- **THEN** the action is denied with reason `authentication_missing` before confirmation or process creation

#### Scenario: Fresh step-up permits later gates

- **WHEN** a scoped high-risk action receives a fresh one-use proof matching its principal, workspace, session, purpose, and canonical action
- **THEN** the authentication gate passes and project policy, containment, and confirmation continue to decide the action

#### Scenario: Ordinary action remains scope-controlled

- **WHEN** an action does not require `high-risk:manage`
- **THEN** it continues through existing scope and lower security gates without requiring a step-up token

#### Scenario: Library compatibility is explicit

- **WHEN** a direct library context leaves the high-risk step-up requirement disabled
- **THEN** the dispatcher preserves its pre-v0.9.6 scope/policy/confirmation behavior and does not represent that context as authenticated

### Requirement: Authentication evidence is masked and auditable

Authentication success, failure, expiry, revocation, replay, and binding mismatch SHALL produce sanitized audit events when durable audit is configured. Authentication event and tool-decision evidence SHALL contain stable outcomes/reasons and only masked references for principal, workspace, action, challenge, and token. Raw verifier/passphrase values, challenge values, response values, opaque tokens, and provider credentials SHALL NOT be written to audit, session, console, policy, or release evidence.

#### Scenario: Lifecycle outcomes are auditable

- **WHEN** authentication succeeds, fails, expires, is revoked, or detects replay
- **THEN** the audit trail identifies the corresponding outcome and stable reason using masked correlation references

#### Scenario: Authentication secrets are absent from persistence

- **WHEN** verifier, response, challenge, and token values are exercised during a sandboxed run
- **THEN** raw audit JSONL, session metadata, session tool logs, console output, and evidence documents contain none of those values

#### Scenario: Tool evidence carries normalized decision

- **WHEN** a high-risk dispatcher decision is attempted
- **THEN** its correlated tool attempt/result metadata records the matching masked authentication decision or denial reason
