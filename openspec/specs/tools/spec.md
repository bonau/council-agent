# Tools

## Purpose

Reusable file system and shell tool functions that return a unified `ToolResult` structure. Introduced in v0.2 as a foundation layer; v0.3 adds WorkspaceGuard boundary enforcement; v0.4 adds `run_tests` with structured pytest reports; v0.5 mounts CrewAI `@tool` wrappers on the Execution Crew; v0.6 gates `run_command` through command classification; v0.7 adds confirmation gates for dangerous/write shell and filesystem mutate tools.

## Requirements

### Requirement: ToolResult unified return structure

All tool functions SHALL return a `ToolResult` dataclass with fields: `success: bool`, `output: str`, `error: str | None`, and `metadata: dict[str, Any]`. The `metadata` field SHALL default to an empty dict.

#### Scenario: Successful tool invocation

- **WHEN** a tool completes without error
- **THEN** it returns `ToolResult(success=True, output=<result>, error=None, metadata=<relevant keys>)`

#### Scenario: Failed tool invocation

- **WHEN** a tool encounters an expected error (file not found, permission denied, non-zero exit code)
- **THEN** it returns `ToolResult(success=False, error=<message>)` without raising an exception

### Requirement: read_file reads workspace files

The system SHALL provide `read_file(path: str) -> ToolResult` that reads a file as UTF-8 text. On success, `metadata` SHALL include `size` (byte count) and `encoding` ("utf-8").

#### Scenario: Read existing file

- **WHEN** `read_file` is called with a path to an existing regular file
- **THEN** it returns `success=True`, `output` containing the file content, and `metadata` with `size` and `encoding`

#### Scenario: Read non-existent file

- **WHEN** `read_file` is called with a path that does not exist
- **THEN** it returns `success=False` with an error message

#### Scenario: Read directory as file

- **WHEN** `read_file` is called with a path that is a directory
- **THEN** it returns `success=False` with an error message

### Requirement: write_file creates or overwrites files

The system SHALL provide `write_file(path: str, content: str) -> ToolResult` that writes UTF-8 text. Parent directories SHALL be created automatically if missing. On success, `metadata` SHALL include `bytes_written` and `created` (True if the file did not exist before write).

#### Scenario: Write new file

- **WHEN** `write_file` is called with a path that does not exist
- **THEN** it creates the file (and parent dirs if needed), returns `success=True`, and `metadata.created` is True

#### Scenario: Overwrite existing file

- **WHEN** `write_file` is called with a path to an existing file
- **THEN** it overwrites the content, returns `success=True`, and `metadata.created` is False

### Requirement: list_dir lists directory entries

The system SHALL provide `list_dir(path: str) -> ToolResult` that lists direct children of a directory. On success, `output` SHALL contain entry names and `metadata.entries` SHALL be a sorted list of entry name strings.

#### Scenario: List populated directory

- **WHEN** `list_dir` is called on a directory with files and subdirectories
- **THEN** it returns `success=True` with all direct child names in `metadata.entries`

#### Scenario: List empty directory

- **WHEN** `list_dir` is called on an empty directory
- **THEN** it returns `success=True` with `metadata.entries` as an empty list

#### Scenario: List non-directory path

- **WHEN** `list_dir` is called on a file path
- **THEN** it returns `success=False` with an error message

### Requirement: delete_file removes files only

The system SHALL provide `delete_file(path: str) -> ToolResult` that deletes a regular file. On success, `metadata.deleted` SHALL be True. Directories SHALL NOT be deleted.

#### Scenario: Delete existing file

- **WHEN** `delete_file` is called on an existing regular file
- **THEN** the file is removed and returns `success=True` with `metadata.deleted=True`

#### Scenario: Delete directory fails

- **WHEN** `delete_file` is called on a directory path
- **THEN** it returns `success=False` with an error message

#### Scenario: Delete non-existent file

- **WHEN** `delete_file` is called on a path that does not exist
- **THEN** it returns `success=False` with an error message

### Requirement: run_command executes shell commands

The system SHALL provide `run_command(command: str, cwd: str | None = None, *, timeout_sec: int = 120) -> ToolResult` that executes a shell command. On completion, `metadata` SHALL include `exit_code` and `duration_ms`. `success` SHALL be True only when exit code is 0.

#### Scenario: Successful command

- **WHEN** `run_command` is executed with a command that exits 0
- **THEN** it returns `success=True`, `output` containing stdout, and `metadata.exit_code` is 0

#### Scenario: Failed command

- **WHEN** `run_command` is executed with a command that exits non-zero
- **THEN** it returns `success=False`, `metadata.exit_code` reflects the exit code, and stderr is in `error` if present

#### Scenario: Command timeout

- **WHEN** `run_command` exceeds `timeout_sec`
- **THEN** it returns `success=False` with a timeout error message

#### Scenario: Command with custom cwd

- **WHEN** `run_command` is called with a `cwd` argument
- **THEN** the command executes in the specified working directory

### Requirement: run_tests executes pytest with structured report

The system SHALL provide `run_tests(path: str = ".", args: str = "", *, timeout_sec: int = 120) -> ToolResult` that runs pytest within the workspace. On completion, `metadata` SHALL include `exit_code`, `passed`, `failed`, `skipped`, and `failures` (list of failure summary strings). `success` SHALL be True only when exit code is 0.

#### Scenario: All tests pass

- **WHEN** `run_tests` is executed and all tests pass
- **THEN** it returns `success=True`, `metadata.exit_code` is 0, and `metadata.failed` is 0

#### Scenario: Some tests fail

- **WHEN** `run_tests` is executed and one or more tests fail
- **THEN** it returns `success=False`, `metadata.exit_code` is non-zero, and `metadata.failures` contains at least one summary string

#### Scenario: Test path outside workspace

- **WHEN** `run_tests` is called with a path outside the workspace root
- **THEN** it returns `success=False` with a workspace boundary error

#### Scenario: Custom pytest args

- **WHEN** `run_tests` is called with additional `args` (e.g. `-k test_foo`)
- **THEN** those arguments are passed to pytest

### Requirement: CrewAI tool wrappers for Execution Crew

The system SHALL expose CrewAI-compatible tools for `read_file`, `write_file`, `list_dir`, `delete_file`, `run_command`, and `run_tests`. Each wrapper SHALL invoke the corresponding standalone function and return a string summary suitable for the agent. Wrappers SHALL route invocations through `ToolCallTracker.record()`.

#### Scenario: Execution agent invokes read_file

- **WHEN** the Execution Crew agent calls the read_file tool with a valid workspace path
- **THEN** the underlying `read_file` function runs and the tracker records the invocation

#### Scenario: Tracker limit stops further tools

- **WHEN** `max_tool_calls` has been reached
- **THEN** subsequent tool wrapper calls return a limit-reached message without executing the underlying function

### Requirement: Workspace boundary enforcement on filesystem tools

All filesystem tool functions (`read_file`, `write_file`, `list_dir`, `delete_file`) SHALL validate the `path` argument via `WorkspaceGuard.resolve()` before performing any file operation. When validation fails, they SHALL return `ToolResult(success=False, error=<message>)` without raising.

#### Scenario: Filesystem tool rejects path outside workspace

- **WHEN** `read_file` is called with a path that resolves outside the workspace root
- **THEN** it returns `success=False` with an error message about workspace boundary

#### Scenario: Filesystem tool rejects denied path

- **WHEN** `read_file` is called with path `.env`
- **THEN** it returns `success=False` with an error message about denied path

#### Scenario: Filesystem tool allows valid workspace path

- **WHEN** `write_file` is called with a path inside the workspace and not denied
- **THEN** it proceeds with the write operation as before

### Requirement: Workspace boundary enforcement on run_command

The `run_command` tool SHALL validate the `cwd` argument via `WorkspaceGuard.resolve_cwd()` before executing. When `cwd` is `None`, the command SHALL execute with workspace root as working directory.

#### Scenario: run_command rejects cwd outside workspace

- **WHEN** `run_command` is called with `cwd` pointing outside the workspace root
- **THEN** it returns `success=False` with an error message about workspace boundary

#### Scenario: run_command defaults to workspace root

- **WHEN** `run_command` is called without `cwd`
- **THEN** the command executes with workspace root as the working directory

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
