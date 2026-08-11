## ADDED Requirements

### Requirement: Project policy trust boundary is restrict-only
The project-root `council.policy.yaml` SHALL be treated as an untrusted, project-owned restriction source, not as user authorization. Its command allowlist SHALL only narrow actions admitted by built-in analysis and later security gates; its command and path denylists SHALL only add denials. Project policy SHALL NOT remove a built-in denial or grant principal scope, authentication, trust grants, Trust Tier, confirmation bypass, or another elevation of authority.

#### Scenario: Command allowlist cannot authorize unsupported action
- **WHEN** project policy lists a command pattern that would match an action rejected by built-in command analysis
- **THEN** the action remains rejected and project policy does not turn it into an accepted or authorized action

#### Scenario: Project policy cannot remove built-in path denial
- **WHEN** a valid project policy omits a built-in sensitive path or supplies only unrelated path restrictions
- **THEN** the built-in sensitive path remains denied

#### Scenario: Authorization-shaped field is rejected
- **WHEN** project policy contains a scope, authentication, grant, Trust Tier, confirmation-bypass, or other unsupported authorization field
- **THEN** the entire policy is rejected as an unknown field before use and no authority is granted

#### Scenario: User-owned trust data remains a separate boundary
- **WHEN** a caller needs persistent user authorization or a revocable trust grant
- **THEN** project policy is not used as that store and this version provides no project-policy field that can create such authorization

## MODIFIED Requirements

### Requirement: Security context is one validated snapshot
Each dispatched action SHALL use exactly one immutable security-context snapshot containing a non-empty request identifier, optional session identifier, workspace guard/root, validated project-policy snapshot and its recognized schema-version label, confirmation policy, tool-call tracker, optional session writer, and optional audit logger. Context validation SHALL reject inconsistent workspace/session, session/audit, or policy/schema-label state before the tool-specific operation runs. Reserved fields for future authorization work SHALL NOT grant principal, authentication, grant, or Trust Tier semantics in this milestone.

#### Scenario: Valid context supplies one action snapshot

- **WHEN** a valid context is active and a tool is invoked
- **THEN** workspace, project policy, policy schema label, confirmation behavior, request/session correlation, and call limit for that invocation all come from that same context object

#### Scenario: Context identity mismatch fails closed

- **WHEN** a context's session workspace or audit session identity does not match the context workspace/session
- **THEN** context installation or invocation is rejected before a tool operation starts

#### Scenario: Versioned policy supplies snapshot label

- **WHEN** a context contains a validated project policy with supported `schema_version: 1`
- **THEN** its policy-version label identifies project-policy schema version 1 for middleware result and audit correlation

#### Scenario: Missing project policy uses built-in label

- **WHEN** a context has no project policy file and uses built-in defaults
- **THEN** its policy-version label identifies the built-in policy state rather than an unversioned project schema

### Requirement: Policy file schema and validation
The system SHALL support an optional project-root policy file named `council.policy.yaml` with required integer `schema_version: 1`. The only project-policy fields supported by schema version 1 SHALL be `schema_version`, `allowed_commands` (list of string patterns), `denied_commands` (list of string patterns), and `denied_paths` (list of string path patterns). Missing or unsupported versions, unknown or misspelled fields, invalid field types, and malformed YAML SHALL reject the entire file before use without silently applying any subset. Validation diagnostics SHALL identify the file, schema-version problem when applicable, and offending field without echoing secret field values. When the file is absent, the system SHALL use built-in defaults without requiring a policy file.

#### Scenario: Version 1 policy loads successfully

- **WHEN** `council.policy.yaml` declares integer `schema_version: 1` and contains only valid version 1 restriction fields
- **THEN** the complete policy is accepted and available as a schema-versioned restriction snapshot

#### Scenario: Unversioned legacy policy is rejected

- **WHEN** an existing v0.9 policy file omits `schema_version`
- **THEN** loading fails with a migration diagnostic requiring `schema_version: 1` and no policy fields are applied

#### Scenario: Unsupported policy version is rejected

- **WHEN** `council.policy.yaml` declares a schema version other than integer 1
- **THEN** loading fails with a diagnostic identifying the unsupported version and the supported version

#### Scenario: Unknown field is rejected

- **WHEN** a version 1 policy contains any unrecognized field
- **THEN** loading fails with a diagnostic identifying that field and no recognized fields are partially applied

#### Scenario: Misspelled security field is rejected

- **WHEN** a version 1 policy contains a misspelling such as `denied_command`
- **THEN** loading fails instead of silently omitting the intended restriction

#### Scenario: Secret value is not echoed in validation error

- **WHEN** an unsupported authorization-shaped field contains a secret-looking value
- **THEN** the validation error identifies the field but does not contain its value

#### Scenario: Invalid known field is rejected

- **WHEN** a version 1 policy gives a known field an invalid type
- **THEN** loading fails with a validation error and the invalid file is not applied

#### Scenario: Missing policy uses defaults

- **WHEN** no `council.policy.yaml` exists at the project root
- **THEN** the system continues with built-in defaults and does not error solely due to the missing file

### Requirement: Allowed command list restricts shell commands
When `allowed_commands` is present and non-empty, a shell command SHALL pass the project-policy layer only if it matches at least one allowed pattern. Matching SHALL NOT override built-in command-analysis rejection, a command or path denial, confirmation policy, or any later authorization gate. Commands that fail the allowlist SHALL be refused before execution even if they would otherwise be classified as `read`. When `allowed_commands` is absent or empty, no allowlist restriction SHALL be added by the project-policy layer.

#### Scenario: Command outside allowlist is refused

- **WHEN** the active policy sets `allowed_commands` to patterns such as `pytest *` and `run_command` is invoked with `echo hello`
- **THEN** the command is not executed and the tool result indicates the command is not allowed by policy

#### Scenario: Command matching allowlist proceeds to later gates

- **WHEN** the active policy allows `echo *` and `run_command` is invoked with `echo hello`
- **THEN** the project-policy filter passes while built-in analysis and later confirmation or authorization gates still decide whether execution may occur

#### Scenario: Allowed pattern does not elevate dangerous action

- **WHEN** a dangerous action matches `allowed_commands` but later requires and fails confirmation
- **THEN** the action remains denied and no subprocess starts

#### Scenario: Empty allowlist means no additional allowlist restriction

- **WHEN** the active policy omits `allowed_commands` or sets it to an empty list
- **THEN** shell commands are not refused solely for failing a project-policy allowlist, while all built-in and later gates remain in force
