## ADDED Requirements

### Requirement: Orchestrator installs confirmation policy for the run

`run_council` SHALL accept a confirmation mode (and optional confirm function for `ask`) and SHALL install that confirmation policy for the duration of the pipeline, including escalation when it runs. The policy SHALL be reset when the run completes or fails.

#### Scenario: Policy active during execution

- **WHEN** `run_council` is invoked with confirmation mode `auto`
- **THEN** tool calls during execution observe `auto` confirmation behavior

#### Scenario: Policy reset after run

- **WHEN** `run_council` completes (success or failure)
- **THEN** the confirmation policy returns to the prior/default context value

### Requirement: CLI passes resolved confirmation mode to orchestrator

The `council run` command SHALL resolve the confirmation mode from `--yes` and TTY detection and SHALL pass that mode into `run_council` without calling tool modules directly from the CLI.

#### Scenario: council run forwards --yes

- **WHEN** the user invokes `council run` with `--yes`
- **THEN** `run_council` receives confirmation mode `auto`
