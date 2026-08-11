## ADDED Requirements

### Requirement: Session records do not constitute authentication

A sandbox session UUID SHALL remain an operational correlation identifier and SHALL NOT establish authentication, freshness, principal presence, or elevated authority. Authentication state SHALL remain outside session metadata and tool-log persistence; session records MAY contain only the masked authentication decision metadata already sanitized by the security evidence layer.

#### Scenario: Loaded session is not authenticated

- **WHEN** an existing `.council/sessions/<session-id>/` record is loaded after a run or restart
- **THEN** its session UUID and tool history do not recreate an authentication challenge or step-up token

#### Scenario: Session log contains no authentication credential

- **WHEN** a sandboxed high-risk decision authenticates or is denied
- **THEN** `meta.json` and `tools.jsonl` contain no raw verifier, challenge, response, or token value

#### Scenario: Runtime session binding is explicit

- **WHEN** a run has no persisted sandbox session
- **THEN** authentication still uses a non-empty process-local runtime session identifier that does not imply durable session storage or authenticated state
