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

### Requirement: Public tool APIs dispatch before execution

The public `read_file`, `write_file`, `list_dir`, `delete_file`, `run_command`, and `run_tests` APIs SHALL send their canonical tool name and typed arguments to the mandatory policy dispatcher. They SHALL NOT perform filesystem access, subprocess creation, policy/confirmation decisions, tracking, session persistence, or audit persistence on a parallel public path.

#### Scenario: Direct library API is dispatcher-backed

- **WHEN** a supported library caller invokes a public tool function under a valid security context
- **THEN** the operation result includes dispatcher request/action correlation and the context tracker contains the invocation summary

#### Scenario: Direct API without context has no side effect

- **WHEN** a public filesystem mutation or shell tool is invoked without a valid security context
- **THEN** it returns a structured context denial and creates no file, subprocess, session record, or audit file

#### Scenario: Crew and direct APIs agree on denial

- **WHEN** equivalent policy, confirmation, workspace, and limit contexts receive the same tool action through a Crew adapter and a direct public function
- **THEN** both results have the same decision and stable denial reason

### Requirement: Raw tool operations are internal security-aware helpers

Raw filesystem and shell operation helpers SHALL be private implementation details, SHALL NOT be exported from the product tool package, and SHALL require the active validated security-context snapshot when they perform a security-sensitive operation. Public callers SHALL use dispatcher-backed APIs. Private helpers are not a separate supported authorization entry point.

#### Scenario: Product package exports no raw executor

- **WHEN** a caller inspects the supported exports of the product tool package
- **THEN** only dispatcher-backed tool functions, result types, and supported tracking types are exposed, with no raw execution function

#### Scenario: Private helper still uses context security state

- **WHEN** dispatcher invokes a private filesystem or shell helper
- **THEN** workspace, project policy, classification, and confirmation checks as applicable use the same validated context snapshot

### Requirement: Composite tools are one dispatched action

A composite product tool such as `run_tests` SHALL consume one tool-call allowance and produce one tracker/session result for its top-level invocation. Its internal argument validation, policy/classification/confirmation checks, and subprocess execution SHALL remain within that action and SHALL NOT recursively invoke a public tool API or create duplicate top-level authorization/audit decisions.

#### Scenario: run_tests consumes one call

- **WHEN** `run_tests` validates arguments, obtains authorization, and runs pytest
- **THEN** the tracker gains exactly one `run_tests` summary with one action identifier

#### Scenario: run_tests denial is not duplicated

- **WHEN** `run_tests` is denied before process creation
- **THEN** middleware emits one top-level attempt/result pair for `run_tests` and no nested `run_command` action

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

The system SHALL provide `run_command(command: str, cwd: str | None = None, *, timeout_sec: int = 120) -> ToolResult` for supported simple commands. A successful input SHALL resolve to exactly one executable and an ordered argument vector and SHALL execute without a shell interpreter or later shell expansion. On process completion, `metadata` SHALL include `exit_code`, `duration_ms`, `classification`, and `matched_rule`; `success` SHALL be True only when exit code is 0. Unsupported, unparseable, shell-control, policy-denied, confirmation-denied, or workspace-boundary inputs SHALL fail before execution with structured refusal metadata and no `exit_code`.

#### Scenario: Successful command

- **WHEN** `run_command` receives a supported simple command that passes all pre-execution gates and exits 0
- **THEN** it returns `success=True`, `output` contains stdout, `metadata.exit_code` is 0, and the submitted process arguments equal the accepted canonical arguments

#### Scenario: Failed command

- **WHEN** a supported command starts and exits non-zero
- **THEN** it returns `success=False`, `metadata.exit_code` reflects the exit code, and stderr is in `error` if present

#### Scenario: Command timeout

- **WHEN** a supported command exceeds `timeout_sec`
- **THEN** it returns `success=False` with a timeout error and `metadata.duration_ms`

#### Scenario: Command with custom cwd

- **WHEN** `run_command` is called with a valid workspace `cwd`
- **THEN** the command executes in that directory and relative path operands are validated relative to that directory

#### Scenario: Quoted whitespace argument

- **WHEN** a supported command receives a quoted argument containing whitespace
- **THEN** the subprocess receives that value as one argument without quote characters or word splitting

#### Scenario: Shell control syntax is not executed

- **WHEN** `run_command` receives a pipeline, redirect, background operator, command substitution, or additional command
- **THEN** it returns `success=False` before process creation and no portion of the input is executed

### Requirement: run_tests executes pytest with structured report

The system SHALL provide `run_tests(path: str = ".", args: str = "", *, timeout_sec: int = 120) -> ToolResult` that runs pytest within the workspace. The validated test path SHALL be passed as one argument even when it contains whitespace, Unicode, quotes, or other legal path characters. Additional `args` SHALL be parsed once into an ordered argument list; they SHALL NOT be concatenated into a shell command, and unsupported shell-control syntax or malformed quoting SHALL be rejected before process creation. The canonical test action SHALL pass active project-policy, explicit classification, and confirmation checks equivalent to `run_command` before execution. On process completion, `metadata` SHALL include `exit_code`, `passed`, `failed`, `skipped`, and `failures`; `success` SHALL be True only when exit code is 0.

#### Scenario: All tests pass

- **WHEN** `run_tests` is executed and all tests pass
- **THEN** it returns `success=True`, `metadata.exit_code` is 0, and `metadata.failed` is 0

#### Scenario: Some tests fail

- **WHEN** `run_tests` is executed and one or more tests fail
- **THEN** it returns `success=False`, `metadata.exit_code` is non-zero, and `metadata.failures` contains at least one summary string

#### Scenario: Test path outside workspace

- **WHEN** `run_tests` is called with a path that resolves outside the workspace root or through an escaping symlink
- **THEN** it returns `success=False` with workspace-boundary refusal metadata and starts no test process

#### Scenario: Custom pytest args

- **WHEN** `run_tests` is called with additional args containing a quoted value such as `-k "test with spaces"`
- **THEN** the quoted value is passed to pytest as one argument and is not reconstructed as shell text

#### Scenario: Test directory name contains spaces

- **WHEN** the validated test path is a workspace directory whose name contains spaces
- **THEN** pytest receives the complete path as one argument and can run the tests in that directory

#### Scenario: Test args cannot inject an additional command

- **WHEN** `args` contains `;`, `&&`, `||`, a pipeline, redirect, newline, backticks, or `$()` command substitution
- **THEN** `run_tests` returns `success=False` with `rejection_reason` set to `shell_metachar`, starts no subprocess, and creates no injected-command side effect

#### Scenario: Test args with malformed quoting are refused

- **WHEN** `args` contains an unclosed quote or otherwise cannot be parsed into arguments
- **THEN** `run_tests` returns `success=False` with `rejection_reason` set to `unparseable` and starts no subprocess

#### Scenario: Test action denied by policy

- **WHEN** the canonical test action does not pass the active command policy
- **THEN** `run_tests` returns the policy refusal before confirmation or process creation

### Requirement: CrewAI tool wrappers for Execution Crew

The system SHALL expose CrewAI-compatible tools for `read_file`, `write_file`, `list_dir`, `delete_file`, `run_command`, and `run_tests`. Each wrapper SHALL only adapt CrewAI typed inputs to the corresponding public dispatcher-backed function and format its `ToolResult` for the agent. Wrappers SHALL NOT own tracker limits, session persistence, policy/confirmation decisions, or audit recording.

#### Scenario: Execution agent invokes read_file

- **WHEN** the Execution Crew agent calls the read_file adapter with a valid active security context and workspace path
- **THEN** the public dispatcher-backed `read_file` function runs and middleware records the invocation in the context tracker

#### Scenario: Tracker limit stops further tools

- **WHEN** the active security context tracker has reached `max_tool_calls`
- **THEN** a subsequent Crew adapter call returns the middleware limit-reached failure without executing the underlying operation

#### Scenario: Wrapper has no independent evidence decisions

- **WHEN** a CrewAI adapter receives a tool result
- **THEN** it only formats that result and does not separately append tracker, session, or audit records

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

The `run_command` tool SHALL validate `cwd` before command analysis and execution. When `cwd` is `None`, the workspace root SHALL be the execution directory. For each supported path-bearing command, all identified path operands SHALL be resolved relative to the validated execution directory when relative, and validated against the workspace boundary, symlink resolution, built-in denied paths, and active-policy denied paths before any process starts.

#### Scenario: run_command rejects cwd outside workspace

- **WHEN** `run_command` is called with `cwd` pointing outside the workspace root
- **THEN** it returns `success=False` with a workspace-boundary error and starts no subprocess

#### Scenario: run_command defaults to workspace root

- **WHEN** `run_command` is called without `cwd`
- **THEN** the workspace root is used as both execution directory and base for relative path-operand validation

#### Scenario: Relative operand uses custom cwd

- **WHEN** a path-bearing command uses relative operand `item.txt` with a valid nested workspace `cwd`
- **THEN** the system validates and executes against `<cwd>/item.txt`, not `<workspace-root>/item.txt`

#### Scenario: Escaping symlink operand is rejected

- **WHEN** a path operand within the workspace resolves through a symlink to a target outside the workspace
- **THEN** `run_command` returns `success=False`, starts no subprocess, and the external target is unchanged

### Requirement: Shell path operands are contained

The supported-command grammar SHALL include path-operand schemas for at least `cat`, `ls`, `rm`, `mv`, `cp`, `touch`, and `mkdir`. Each schema SHALL distinguish recognized options from path operands, support the `--` end-of-options marker where applicable, and identify every source and destination path before execution. If an option form makes path identification ambiguous or is not supported by that command schema, the action SHALL be refused with `rejection_reason` set to `unsupported`.

#### Scenario: Relative read path inside workspace is allowed

- **WHEN** `cat` or `ls` receives a relative path that resolves inside the workspace and is not denied
- **THEN** path validation passes and the action may proceed to policy and confirmation gates

#### Scenario: Absolute write path inside workspace is allowed

- **WHEN** `touch` or `mkdir` receives an absolute path inside the workspace and all later gates allow it
- **THEN** the command may execute against that path

#### Scenario: Outside destination is refused without side effect

- **WHEN** `cp` or `mv` has a destination path outside the workspace
- **THEN** the action is refused before process creation and neither source nor destination is changed

#### Scenario: Every multi-path operand is validated

- **WHEN** `cp`, `mv`, or another supported multi-path command has both inside-workspace and outside-workspace operands
- **THEN** one invalid operand refuses the entire action before process creation

#### Scenario: Path beginning with dash uses end-of-options marker

- **WHEN** a supported command identifies `--` followed by a workspace path whose filename begins with `-`
- **THEN** that value is validated as a path operand rather than interpreted as an option

#### Scenario: Ambiguous path option is refused

- **WHEN** a command uses an option form whose path semantics are not defined by its supported-command schema
- **THEN** the entire action is refused with `rejection_reason` set to `unsupported`

### Requirement: Pre-execution shell refusals are structured and side-effect free

Any command rejected before process creation SHALL return `ToolResult(success=False)` with a human-readable `error`, a stable `metadata.rejection_reason`, and no `metadata.exit_code`. Supported refusal reasons SHALL include `unsupported`, `unparseable`, `shell_metachar`, `workspace_boundary`, and `denied_path`. A pre-execution refusal SHALL start no subprocess and SHALL cause no command, filesystem, process, or network side effect.

#### Scenario: Unsupported executable returns structured refusal

- **WHEN** `run_command` receives an executable that is not in the explicit supported-command registry
- **THEN** it returns `success=False`, `metadata.rejection_reason` is `unsupported`, `metadata` has no `exit_code`, and no subprocess starts

#### Scenario: Outside path returns structured refusal

- **WHEN** a recognized path operand resolves outside the workspace
- **THEN** it returns `success=False`, `metadata.rejection_reason` is `workspace_boundary`, `metadata` has no `exit_code`, and the outside sentinel is unchanged

#### Scenario: Denied path returns structured refusal

- **WHEN** a recognized path operand resolves to a built-in or active-policy denied path
- **THEN** it returns `success=False`, `metadata.rejection_reason` is `denied_path`, and no subprocess starts

#### Scenario: Compound syntax has no partial execution

- **WHEN** the first textual segment of a compound command would be valid but a later segment contains a side effect
- **THEN** the entire input is refused before process creation and neither segment executes

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

### Requirement: run_command applies project policy before execution

`run_command` SHALL evaluate the active project policy against a stable representation of the same canonical executable and ordered arguments that would be executed. Policy denial (denied pattern or failed allowlist) SHALL return `success=False` with an error describing the policy decision and SHALL NOT execute the command. Policy checks SHALL occur after command analysis and path validation and before confirmation prompts for the same accepted action.

#### Scenario: Policy-denied command does not run

- **WHEN** an accepted canonical action matches an active `denied_commands` pattern
- **THEN** the result has `success=False`, the error mentions policy denial, and no subprocess is started

#### Scenario: Policy check precedes confirmation

- **WHEN** an accepted action would require confirmation and also matches a denied policy pattern
- **THEN** the tool returns a policy denial without prompting for confirmation

#### Scenario: Allowed-by-policy command still subject to classification

- **WHEN** a canonical action passes policy allow/deny checks and has a dangerous classification
- **THEN** the existing dangerous-action confirmation gate still applies

#### Scenario: Policy and execution use the same action

- **WHEN** a command passes policy evaluation
- **THEN** no shell expansion or reparsing can change its executable or ordered arguments before process creation

### Requirement: Product tools cannot target control-plane paths

Every dispatcher-backed filesystem tool and every recognized shell path operand SHALL apply the built-in control-plane denylist before any read, mutation, or subprocess start. A project policy SHALL NOT remove this denial. Refusal SHALL be structured and SHALL leave the targeted audit, session, sandbox configuration, reserved authorization, or project-policy sentinel unchanged.

#### Scenario: Filesystem mutation cannot alter control plane

- **WHEN** `write_file` or `delete_file` targets a root or nested protected audit, session, sandbox configuration, reserved authorization, or policy path
- **THEN** the tool returns a denied-path failure and the target remains unchanged

#### Scenario: Shell mutation cannot alter control plane

- **WHEN** a supported `rm`, `mv`, `cp`, `touch`, or `mkdir` action includes a protected control-plane operand
- **THEN** the entire action is refused before process creation and every source and target sentinel remains unchanged

#### Scenario: Shell read cannot expose control plane

- **WHEN** a supported `cat` or path-targeted `ls` action includes a protected control-plane operand
- **THEN** the action is refused before process creation with no control-plane content returned

#### Scenario: Test process remains outside claim

- **WHEN** project code is executed through `run_tests`
- **THEN** the product does not claim the path denylist is an operating-system sandbox for that project process
