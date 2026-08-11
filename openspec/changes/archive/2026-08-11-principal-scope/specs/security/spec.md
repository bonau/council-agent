## MODIFIED Requirements

### Requirement: Security context is one validated snapshot

Each dispatched action SHALL use exactly one immutable security-context snapshot containing a non-empty request identifier, optional session identifier, workspace guard/root, validated project-policy snapshot and its recognized schema-version label, confirmation policy, tool-call tracker, optional session writer, optional audit logger, and one expected Council principal identity with a current-authority resolver. Context validation SHALL reject inconsistent workspace/session, session/audit, policy/schema-label, or principal-binding state before the tool-specific operation runs. The principal binding SHALL NOT represent session authentication, a trust grant, or Trust Tier state.

#### Scenario: Valid context supplies one action snapshot

- **WHEN** a valid context is active and a tool is invoked
- **THEN** workspace, project policy, policy schema label, confirmation behavior, request/session correlation, expected principal identity, and call limit for that invocation all come from that same context object

#### Scenario: Context identity mismatch fails closed

- **WHEN** a context's session workspace, audit session identity, or resolved principal identity does not match the context's bound workspace, session, or expected principal
- **THEN** context installation or invocation is rejected before a tool operation starts

#### Scenario: Versioned policy supplies snapshot label

- **WHEN** a context contains a validated project policy with supported `schema_version: 1`
- **THEN** its policy-version label identifies project-policy schema version 1 for middleware result and audit correlation

#### Scenario: Policy label does not create a versioned schema

- **WHEN** a caller attempts to pair an arbitrary or legacy policy-version label with an absent or mismatched policy snapshot
- **THEN** context validation rejects the mismatch because a label alone cannot validate or create a project-policy schema

#### Scenario: Missing project policy uses built-in label

- **WHEN** a context has no project policy file and uses built-in defaults
- **THEN** its policy-version label identifies the built-in policy state rather than an unversioned project schema

## ADDED Requirements

### Requirement: Council principals are distinct from provider credentials

A Council authorization principal SHALL have a non-empty stable identifier, recognized principal kind, non-empty issuer/source, and an explicit set of recognized Council scopes. The OpenRouter API key SHALL be represented and loaded only as a model-provider credential and SHALL NOT be accepted as a Council principal, principal identifier, scope source, authentication proof, trust grant, or audit identity.

#### Scenario: Provider key cannot authorize a tool

- **WHEN** a caller supplies an OpenRouter provider credential but omits the Council principal
- **THEN** model credential handling remains separate and every dispatched tool action fails closed for missing principal

#### Scenario: Invalid principal is rejected

- **WHEN** a principal has an empty identifier or issuer, an unknown kind, or an unknown scope
- **THEN** it is rejected before any tool action executes

#### Scenario: Stable principal identity is preserved

- **WHEN** the same issuer, kind, and principal identifier is used across multiple decisions
- **THEN** those decisions have the same stable masked principal reference without exposing the raw identifier

### Requirement: Principal scopes are explicit and fail closed

The recognized Council scope set SHALL include exactly defined values for read, filesystem mutation, test execution, shell execution, and high-risk management. Before any registered product tool operation, the dispatcher SHALL resolve the current principal and require every scope assigned to the canonical top-level action. Missing, invalid, identity-mismatched, or insufficient authority SHALL return a structured denial with stable reason metadata and SHALL NOT be overridden by project policy, confirmation mode, `--yes`, wrappers, or composite-tool internals.

#### Scenario: Missing principal is denied

- **WHEN** a valid security context has no current Council principal
- **THEN** the action is denied with reason `principal_missing` before the handler, filesystem, or subprocess runs

#### Scenario: Unknown scope fails closed

- **WHEN** current principal authority contains a scope outside the recognized scope set
- **THEN** the action is denied as an invalid principal and no operation starts

#### Scenario: Insufficient scope is denied

- **WHEN** a valid principal lacks one or more scopes required by the requested action
- **THEN** the action is denied with reason `scope_insufficient` and reports masked principal, required, granted, and missing scopes

#### Scenario: Confirmation cannot elevate scope

- **WHEN** a principal lacks a required scope while confirmation mode is `auto` or an interactive confirmation would approve
- **THEN** the dispatcher denies before confirmation and does not elevate the principal

### Requirement: Current principal authority is evaluated per action

Every dispatched action SHALL resolve current principal authority again and SHALL compare its issuer, kind, and stable identifier to the identity bound into the security context. Scope reductions SHALL affect the next action. An absent current principal SHALL be treated as revoked for that decision, and a substituted identity SHALL fail closed. This per-action resolution SHALL NOT provide a persistent grant store or session authentication.

#### Scenario: Scope tightening applies immediately

- **WHEN** a principal source returns fewer scopes after one allowed action
- **THEN** the next action uses the reduced scope set and is denied if its required scope was removed

#### Scenario: Revocation applies immediately

- **WHEN** a principal source returns no current principal after one allowed action
- **THEN** the next action is denied with reason `principal_revoked` and does not use the prior principal snapshot

#### Scenario: Principal substitution is denied

- **WHEN** a current-principal source returns a different issuer, kind, or stable identifier from the context-bound identity
- **THEN** the action is denied with reason `principal_mismatch`

### Requirement: Audit evidence records masked scope decisions

Middleware attempt and result evidence SHALL include a recursively sanitized authorization decision containing a masked stable principal reference when available, recognized principal kind, required scopes, granted scopes, missing scopes, allow/deny outcome, and stable authorization reason. Raw provider credentials, Council credentials, and raw principal identifiers SHALL NOT be persisted in audit or session evidence.

#### Scenario: Allowed decision is auditable

- **WHEN** a scoped principal is allowed to execute an action with durable audit enabled
- **THEN** the correlated attempt and result contain the same masked principal reference and allowed scope decision

#### Scenario: Denied decision is auditable

- **WHEN** scope authorization denies an action with durable audit enabled
- **THEN** the correlated attempt and result contain a denied scope decision and stable reason without invoking the operation

#### Scenario: Credential and raw identity are not persisted

- **WHEN** provider credential text or a secret-looking raw principal identifier is present in runtime inputs
- **THEN** neither value appears in stored audit or session evidence
