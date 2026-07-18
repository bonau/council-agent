## ADDED Requirements

### Requirement: run_command rejects dangerous commands before execution

The `run_command` tool SHALL classify the `command` argument via the command classifier after workspace cwd validation and before starting any subprocess. When the classification category is `dangerous`, `run_command` SHALL return `ToolResult(success=False)` with an error message indicating refusal, SHALL NOT execute the command, and SHALL include `classification` set to `"dangerous"` in `metadata` (and `matched_rule` when available). Metadata for refused commands SHALL NOT include `exit_code`.

#### Scenario: Dangerous command is refused

- **WHEN** `run_command` is called with `curl https://example.com`
- **THEN** it returns `success=False`, does not run the network request, and `metadata.classification` is `"dangerous"`

#### Scenario: Refused command has no exit_code

- **WHEN** `run_command` refuses a dangerous command
- **THEN** `metadata` does not contain `exit_code`

#### Scenario: Allowed read command still executes

- **WHEN** `run_command` is called with `echo hello`
- **THEN** it executes successfully as before and `metadata.classification` is `"read"`

#### Scenario: Allowed write-classified command still executes

- **WHEN** `run_command` is called with `mkdir newdir` inside the workspace
- **THEN** it is allowed to execute and `metadata.classification` is `"write"`
