## ADDED Requirements

### Requirement: CLI provides authenticated trust-store administration
The CLI SHALL provide `council trust grant`, `council trust revoke`, and `council trust list` as local user-owned store administration commands. The commands SHALL resolve the local Council principal independently from the model-provider credential, require the dedicated authentication verifier without accepting a command-line secret, bind fresh authentication to the exact command arguments, and return a non-zero status on authentication, validation, ownership, permission, schema, corruption, conflict, expiry, or persistence failure.

#### Scenario: Authenticated grant is displayed
- **WHEN** a scoped local principal invokes `council trust grant` with a recognized action, JSON resource object, valid scopes, optional aware expiry, and configured authentication verifier
- **THEN** the command persists one exact grant and displays its grant ID without displaying authentication material

#### Scenario: Revoke survives a later invocation
- **WHEN** a scoped authenticated principal revokes one of its grant IDs and later invokes list in a new process
- **THEN** the revoked grant is not active and cannot be restored by workspace state

#### Scenario: List requires authentication but no provider key authority
- **WHEN** a read-scoped principal invokes `council trust list`
- **THEN** the command requires fresh trust-management authentication and does not treat the OpenRouter API key, session ID, `--yes`, or project policy as that proof

#### Scenario: Missing verifier fails without mutation
- **WHEN** grant, revoke, or list is invoked without the dedicated authentication verifier
- **THEN** the command exits non-zero without creating or changing trust-grant state

### Requirement: Trust CLI is a store foundation rather than Trust Tier runtime
The trust CLI SHALL manage and inspect persistent grant records only. It SHALL NOT expose a Trust Tier setting, alter product-tool dispatcher decisions, bypass principal scope or project-policy denial, convert confirmation into a persistent grant, or claim Tier 0/1/2 behavior.

#### Scenario: Stored grant does not change a tool decision
- **WHEN** a grant exists and a Council product tool is invoked in v0.9.7
- **THEN** the existing principal, authentication, project-policy, confirmation, and dispatcher behavior remains unchanged because grant consumption is not connected
