## MODIFIED Requirements

### Requirement: run_council installs project policy for the pipeline
`run_council` SHALL attempt to load the resolved project-root `council.policy.yaml` before creating a session, security context, audit writer, or any crew. When the file is missing, the context SHALL contain no project policy, SHALL use built-in defaults, and SHALL carry the built-in policy-version label. When the file exists, the orchestrator SHALL require one complete supported schema-version policy; any malformed YAML, missing or unsupported version, unknown field, misspelled field, or invalid known field SHALL fail fast without installing any policy subset. A valid loaded policy and its schema-version label SHALL be stored in the one context snapshot and removed together when that context is cleaned up.

#### Scenario: Valid versioned policy installed for run

- **WHEN** `run_council` starts and a valid `schema_version: 1` `council.policy.yaml` exists at the resolved project root
- **THEN** the resulting security context snapshot supplies that complete restrict-only policy and its version 1 label to dispatched tool and path evaluation during the run

#### Scenario: Missing policy file does not fail the run

- **WHEN** `run_council` starts and no `council.policy.yaml` exists
- **THEN** the pipeline continues with a valid security context whose project policy is absent, whose evaluators use built-in defaults, and whose policy-version label identifies that built-in state

#### Scenario: Invalid policy fails before runtime state

- **WHEN** `run_council` starts and `council.policy.yaml` has invalid YAML, schema version, fields, or field types
- **THEN** the run aborts with a sanitized validation error before a session, audit writer, security context, or crew is created

#### Scenario: Unknown field cannot be partially applied

- **WHEN** a policy contains valid denial fields together with an unknown or misspelled field
- **THEN** the orchestrator rejects the whole file and does not start a run using only the recognized denials

#### Scenario: Policy reset after run

- **WHEN** a `run_council` invocation finishes after loading a valid versioned policy
- **THEN** context cleanup prevents later callers from inheriting either that policy snapshot or its schema-version label
