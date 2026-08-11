## MODIFIED Requirements

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

- **WHEN** `run_tests` executes and all tests pass
- **THEN** it returns `success=True`, `metadata.exit_code` is 0, and `metadata.failed` is 0

#### Scenario: Some tests fail

- **WHEN** `run_tests` executes and one or more tests fail
- **THEN** it returns `success=False`, `metadata.exit_code` is non-zero, and `metadata.failures` contains at least one summary

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

## ADDED Requirements

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
