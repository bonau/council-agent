## ADDED Requirements

### Requirement: run_council installs project policy for the pipeline

`run_council` SHALL attempt to load `council.policy.yaml` from the resolved workspace/project root and install it as the active policy for the duration of the pipeline. When the file is missing, the run SHALL proceed with no installed policy (built-in defaults). When the file exists but fails validation, the run SHALL fail fast with a clear error before executing crews. The active policy SHALL be reset after the run completes (including on failure).

#### Scenario: Valid policy installed for run

- **WHEN** `run_council` starts and a valid `council.policy.yaml` exists at the project root
- **THEN** the policy is active for tool and path evaluation during that run

#### Scenario: Missing policy file does not fail the run

- **WHEN** `run_council` starts and no `council.policy.yaml` exists
- **THEN** the pipeline continues using built-in defaults

#### Scenario: Invalid policy fails before crews

- **WHEN** `run_council` starts and `council.policy.yaml` fails validation
- **THEN** the run aborts with a validation error and crews are not executed

#### Scenario: Policy reset after run

- **WHEN** a `run_council` invocation finishes (success or failure) after installing a policy
- **THEN** the active policy context is reset so later callers do not inherit that policy
