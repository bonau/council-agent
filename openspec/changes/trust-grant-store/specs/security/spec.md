## ADDED Requirements

### Requirement: Trust grants use a user-owned store outside the workspace
Persistent trust grants SHALL be loaded only from a canonical user-data location outside the active workspace. Before creating, reading, locking, auditing, or replacing store data, the system SHALL verify that every existing store component is non-symlink user-owned state with no group or other access, and SHALL fail closed on unsupported ownership checks, permission errors, workspace overlap, unsafe ancestors, or path replacement.

#### Scenario: Secure user-owned store is accepted
- **WHEN** the grant root is outside the workspace, owned by the current user, and accessible only to that user
- **THEN** the system may initialize directories and files with restrictive user-only permissions

#### Scenario: Workspace-local store is refused
- **WHEN** a configured grant-store path resolves inside the active workspace
- **THEN** the system refuses the operation without creating, reading, or replacing grant state

#### Scenario: Ownership or permission validation fails closed
- **WHEN** the store root, state file, lock, audit path, or an existing path component has a different owner, unsafe permissions, is a symlink, or cannot be securely inspected
- **THEN** the entire requested operation is refused and no grant is adopted or changed

### Requirement: Grant records have exact canonical authority bindings
Each grant SHALL have a unique opaque ID and SHALL bind one masked Council principal identity, one recognized canonical top-level action, one canonical JSON resource object, a non-empty closed set of Council scopes, the masked creating principal, a timezone-aware creation timestamp, and an optional later expiry. Canonicalization SHALL reject unknown actions, non-object or non-finite resources, unrecognized scopes, naive timestamps, wildcard authority, and a grant scope not already held by the subject and creator.

#### Scenario: Exact grant is persisted
- **WHEN** an authenticated principal creates a grant for itself using a recognized action, exact resource object, and a subset of its current scopes
- **THEN** the stored record contains the exact canonical bindings, creator, timestamps, and one new unique ID

#### Scenario: Grant cannot expand current scope
- **WHEN** a requested grant contains a scope that the current principal does not hold
- **THEN** creation is denied before persistent state changes

#### Scenario: Semantically equal resources have one canonical form
- **WHEN** equivalent resource objects differ only in key ordering or insignificant JSON whitespace
- **THEN** they resolve to the same canonical resource and cannot create conflicting live grants

### Requirement: Trust grant administration requires fresh authentication
Grant, revoke, and list operations SHALL require a current Council principal with the operation's required scope and fresh one-use authentication bound to that principal, the canonical store, a non-empty management session, the exact operation, and its canonical arguments. Grant and revoke SHALL require `high-risk:manage`; list SHALL require `read`. Session IDs, provider credentials, project policy, confirmation, `ConfirmMode.AUTO`, `--yes`, and Agent workspace writes SHALL NOT satisfy authentication, create a grant, restore a revoked grant, or expand grant scope.

#### Scenario: Missing authentication cannot create state
- **WHEN** a fully scoped principal requests a grant without fresh management authentication
- **THEN** creation is denied and the store remains unchanged

#### Scenario: Authentication is exact-operation bound
- **WHEN** authentication issued for list, a different grant target, another store, another principal, or another session is presented to grant or revoke
- **THEN** the operation is denied without changing state

#### Scenario: Project-controlled input cannot grant authority
- **WHEN** project policy, workspace files, confirmation auto mode, or `--yes` requests broader or restored authority
- **THEN** no grant-store administration authentication is created and no grant changes

### Requirement: Invalid and inactive grant state is never adopted
The store SHALL use one strict integer schema version and SHALL reject the complete document on malformed encoding or JSON, unknown fields, unknown or non-integer schema, invalid records, duplicate IDs, duplicate or conflicting live bindings, or inconsistent revocation data. Revoked grants SHALL become inactive immediately for the next locked lookup and across process restart. Expired grants SHALL be inactive at expiry, and clock rollback or invalid time relationships SHALL fail closed.

#### Scenario: Revoke applies to the next lookup
- **WHEN** an authenticated principal revokes an active grant
- **THEN** the same grant is inactive for the next lookup and remains inactive after reopening the store

#### Scenario: Expired grant is ignored
- **WHEN** current UTC time is at or after a grant's expiry
- **THEN** lookup and active listing do not adopt the grant

#### Scenario: Corrupt or future state fails closed
- **WHEN** the store contains malformed data, duplicate/conflicting records, unknown fields, or an unsupported schema version
- **THEN** list, lookup, grant, and revoke refuse the whole store rather than using a partial or legacy interpretation

### Requirement: Grant mutations are atomic and serialized
Every grant or revoke mutation SHALL take exclusive inter-process ownership of a validated user-owned lock, re-read and validate current state while locked, write a complete same-directory temporary file with user-only permissions, durably flush it, atomically replace the state file, and durably flush the containing directory. A failed write, flush, replace, lock, or post-replace validation SHALL be reported explicitly and SHALL never expose a partially written store as valid state.

#### Scenario: Concurrent grants preserve both updates
- **WHEN** two processes request valid non-conflicting grants concurrently
- **THEN** serialized read-modify-replace commits preserve both complete records without lost updates

#### Scenario: Interrupted replacement is not adopted
- **WHEN** temporary-file writing or replacement fails
- **THEN** a later read sees either the prior complete store or the new complete store, never a partial document

### Requirement: Trust grant decisions produce masked audit evidence
Every grant, revoke, list, and lookup decision SHALL emit correlated administrative evidence to the user-owned trust control plane before returning success. Evidence SHALL include the operation, allow or deny result, stable reason, management session or request correlation, grant ID reference when applicable, masked principal and creator references, canonical action reference, resource reference, and scope names, while excluding raw principal IDs, raw resources, authentication verifier/challenge/response/token values, and unmasked grant IDs.

#### Scenario: Successful management evidence is masked
- **WHEN** an authenticated grant or revoke operation succeeds
- **THEN** audit evidence correlates the decision using only masked identity, target, and grant references

#### Scenario: Refusal evidence is masked
- **WHEN** authentication, validation, expiry, conflict, ownership, or permission checks deny an operation after the audit boundary is safely available
- **THEN** a masked denial reason is recorded without credential or resource disclosure

### Requirement: Trust store recovery preserves fail-closed semantics
Backup and recovery guidance SHALL require offline user-controlled copying with user-only permissions, validation before replacement, no schema downgrade, and preservation of newer revocations. The implementation SHALL provide a validation-only operation that never repairs, migrates, truncates, or partially adopts invalid state automatically.

#### Scenario: Validation does not repair corruption
- **WHEN** an operator validates a corrupted or unsupported backup
- **THEN** validation reports refusal and leaves both active state and backup unchanged

#### Scenario: Schema downgrade is refused
- **WHEN** a store or backup declares an older unrecognized or future schema
- **THEN** it is refused without automatic downgrade or partial migration
