## ADDED Requirements

### Requirement: Product tools enforce the canonical scope matrix

Before a public tool handler or composite-tool internal operation runs, the mandatory dispatcher SHALL authorize the top-level action against the current Council principal using this cumulative scope matrix:

- `read_file` and `list_dir` SHALL require `read`.
- `write_file` and `delete_file` SHALL require `filesystem:mutate`.
- `run_tests` SHALL require both `test` and `filesystem:mutate`.
- `run_command` SHALL require `shell` plus `read` for read-classified commands, `filesystem:mutate` for write-classified commands, and both `filesystem:mutate` and `high-risk:manage` for dangerous-classified commands.

Any missing required scope SHALL deny the complete action before filesystem access, subprocess creation, policy evaluation, or confirmation. A wrapper, project allowlist, confirmation outcome, or composite child operation SHALL NOT reduce this matrix.

#### Scenario: Read scope permits direct reads only

- **WHEN** a principal has only `read`
- **THEN** `read_file` and `list_dir` may proceed to later gates while filesystem mutation, tests, and shell actions are denied by scope

#### Scenario: Filesystem mutation requires mutate scope

- **WHEN** a principal without `filesystem:mutate` calls `write_file` or `delete_file`
- **THEN** the dispatcher denies before path mutation and the target remains unchanged

#### Scenario: Test action requires test and mutate scopes

- **WHEN** a principal has `test` without `filesystem:mutate`, or `filesystem:mutate` without `test`
- **THEN** `run_tests` is denied before pytest starts because project tests can mutate the workspace

#### Scenario: Read-only principal cannot use composite test path

- **WHEN** a principal with only `read` invokes `run_tests` directly or through a CrewAI wrapper
- **THEN** one top-level scope denial is returned, no nested action is authorized, no test process starts, and mutation sentinels remain unchanged

#### Scenario: Shell read requires shell and read scopes

- **WHEN** a principal lacks either `shell` or `read` and invokes a read-classified shell command
- **THEN** the command is denied before process creation

#### Scenario: Shell write requires shell and mutate scopes

- **WHEN** a principal lacks either `shell` or `filesystem:mutate` and invokes a write-classified shell command
- **THEN** the command is denied before process creation and filesystem sentinels remain unchanged

#### Scenario: Dangerous shell requires high-risk authority

- **WHEN** a principal lacks any of `shell`, `filesystem:mutate`, or `high-risk:manage` and invokes a dangerous-classified shell command
- **THEN** the command is denied by scope before project policy or confirmation can permit it

### Requirement: Scope denial is one side-effect-free dispatched result

A scope-denied public or wrapped tool call SHALL consume no tracker allowance for an executed operation, SHALL produce no handler, filesystem, process, or network side effect, and SHALL return one correlated top-level denial result. When durable evidence is configured, middleware SHALL emit exactly one correlated attempt/result pair for that denial.

#### Scenario: Direct and wrapped denial agree

- **WHEN** equivalent principals and contexts invoke the same insufficiently scoped action through a direct API and a CrewAI adapter
- **THEN** both return the same stable scope-denial reason and neither invokes a raw tool handler

#### Scenario: Denied composite action is not duplicated

- **WHEN** `run_tests` is denied for insufficient scope
- **THEN** it produces one authorization decision and no nested `run_command`, tracker, session, or audit decision
