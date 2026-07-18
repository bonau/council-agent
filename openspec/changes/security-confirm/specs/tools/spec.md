## ADDED Requirements

### Requirement: run_command gates write-classified commands through confirmation

When `run_command` classifies a command as `write`, it SHALL consult the confirmation gate before starting any subprocess. When the gate denies, `run_command` SHALL return `ToolResult(success=False)` without executing the command, SHALL include `classification` set to `"write"` in `metadata`, and SHALL include a `confirmation` outcome of `denied` or `refused`. Metadata for denied commands SHALL NOT include `exit_code`.

#### Scenario: Write command denied in refuse mode

- **WHEN** confirmation mode is `refuse` and `run_command` is called with `mkdir newdir`
- **THEN** it returns `success=False`, does not create the directory, `metadata.classification` is `"write"`, and `metadata` has no `exit_code`

#### Scenario: Write command allowed in auto mode

- **WHEN** confirmation mode is `auto` and `run_command` is called with `mkdir newdir` inside the workspace
- **THEN** it may execute and `metadata.classification` is `"write"` with `confirmation` set to `"auto"`

### Requirement: Filesystem mutate tools require confirmation

`write_file` and `delete_file` SHALL consult the confirmation gate after workspace path validation and before performing any filesystem mutation. When the gate denies, they SHALL return `ToolResult(success=False)` without mutating the filesystem and SHALL include a `confirmation` outcome of `denied` or `refused` in `metadata`. `read_file` and `list_dir` SHALL NOT require confirmation.

#### Scenario: write_file denied leaves file unchanged

- **WHEN** confirmation mode is `refuse` and `write_file` is called for a new path
- **THEN** it returns `success=False` and the file is not created

#### Scenario: delete_file denied leaves file present

- **WHEN** confirmation mode is `refuse` and `delete_file` is called on an existing file
- **THEN** it returns `success=False` and the file still exists

#### Scenario: read_file does not require confirmation

- **WHEN** confirmation mode is `refuse` and `read_file` is called on an existing file
- **THEN** it reads successfully without a confirmation prompt

## MODIFIED Requirements

### Requirement: run_command rejects dangerous commands before execution

The `run_command` tool SHALL classify the `command` argument via the command classifier after workspace cwd validation and before starting any subprocess. When the classification category is `dangerous`, `run_command` SHALL consult the confirmation gate. When the gate denies (including `compat` and `refuse` modes, and `ask` with a negative answer), `run_command` SHALL return `ToolResult(success=False)` with an error message indicating refusal, SHALL NOT execute the command, and SHALL include `classification` set to `"dangerous"` in `metadata` (and `matched_rule` when available) plus a `confirmation` outcome of `denied` or `refused`. Metadata for refused commands SHALL NOT include `exit_code`. When the gate allows (`auto`, or `ask` with affirmative answer), `run_command` MAY execute the command and SHALL include `confirmation` set to `"auto"` or `"approved"` as appropriate.

#### Scenario: Dangerous command is refused

- **WHEN** `run_command` is called with `curl https://example.com` under `compat` or `refuse` mode
- **THEN** it returns `success=False`, does not run the network request, and `metadata.classification` is `"dangerous"`

#### Scenario: Refused command has no exit_code

- **WHEN** `run_command` refuses a dangerous command
- **THEN** `metadata` does not contain `exit_code`

#### Scenario: Allowed read command still executes

- **WHEN** `run_command` is called with `echo hello`
- **THEN** it executes successfully as before and `metadata.classification` is `"read"`

#### Scenario: Allowed write-classified command still executes

- **WHEN** `run_command` is called with `mkdir newdir` inside the workspace under `compat` or `auto` mode
- **THEN** it is allowed to execute and `metadata.classification` is `"write"`

#### Scenario: Dangerous command allowed after confirmation

- **WHEN** confirmation mode is `ask`, the confirm function returns True, and `run_command` is called with a dangerous command
- **THEN** the command is permitted to execute and `metadata.confirmation` is `"approved"`
