# Security

## Purpose

Fail-closed command analysis, interactive confirmation gates, structured audit logging, and project policy files for shell and filesystem tools. Introduced in v0.6 (classification), v0.7 (confirmation), v0.8 (audit), and v0.9 (policy), with simple-command containment hardened in v0.9.1; later milestones add trust tiers.

## Requirements

### Requirement: Command classification categories

The system SHALL analyze a command as one supported simple action before assigning a risk category. An accepted action SHALL have a category of exactly one of `read`, `write`, or `dangerous`, and SHALL match an explicit supported-command rule; an unknown executable or unsupported command form SHALL be rejected and SHALL NOT default to `read`. Dangerous rules SHALL take precedence over write rules.

#### Scenario: Read command classified as read

- **WHEN** a supported read command such as `echo hello`, `ls`, or `cat README.md` is analyzed
- **THEN** the action is accepted with category `read`

#### Scenario: Write command classified as write

- **WHEN** a supported write command such as `mkdir foo`, `touch a.txt`, or `mv a b` is analyzed
- **THEN** the action is accepted with category `write`

#### Scenario: Dangerous command classified as dangerous

- **WHEN** a supported dangerous command such as `sudo ls`, `curl https://example.com`, or `rm -rf build` is analyzed
- **THEN** the action is accepted for later policy and confirmation gates with category `dangerous`

#### Scenario: Dangerous takes precedence over write

- **WHEN** a supported action matches both a dangerous rule and a write rule
- **THEN** the accepted category is `dangerous`

#### Scenario: Unknown command does not default to read

- **WHEN** a command names an executable for which no supported-command rule exists
- **THEN** analysis rejects the command with reason `unsupported` and does not assign category `read`

### Requirement: Dangerous command patterns cover ROADMAP defaults

The classifier SHALL treat at least the following as `dangerous`: `sudo`, `curl`, `wget`, `chmod`, `chown`, recursive/force `rm` (e.g. `rm -rf`, `rm -fr`, or combined `-r`/`-f` flags), `mkfs`, `dd`, `shutdown`, and `reboot`.

#### Scenario: sudo is dangerous

- **WHEN** `classify_command` is called with `sudo apt update`
- **THEN** the category is `dangerous`

#### Scenario: curl is dangerous

- **WHEN** `classify_command` is called with `curl https://example.com`
- **THEN** the category is `dangerous`

#### Scenario: rm -rf is dangerous

- **WHEN** `classify_command` is called with `rm -rf build`
- **THEN** the category is `dangerous`

### Requirement: Classification result includes matched rule

Every accepted command analysis result SHALL include a non-empty `matched_rule` identifying the explicit rule that assigned its category. Every rejected analysis result SHALL instead include a stable `rejection_reason` of `unsupported`, `unparseable`, or `shell_metachar`, as applicable.

#### Scenario: Dangerous match exposes rule id

- **WHEN** a supported command such as `sudo true` is analyzed successfully
- **THEN** `matched_rule` is a non-empty identifier for the rule that accepted and categorized the action

#### Scenario: Rejected command exposes reason code

- **WHEN** command analysis rejects an unknown, malformed, or compound-shell input
- **THEN** the result exposes the corresponding stable `rejection_reason` and does not represent the input as an accepted read action

### Requirement: Supported command grammar is fail-closed

The command analyzer SHALL accept only one non-empty, parseable simple command with no shell control syntax. Inputs containing shell metacharacters or control forms, including `;`, `|`, `&`, backticks, `$`, command substitution, `<`, `>`, carriage returns, or newlines, SHALL be rejected with reason `shell_metachar` even when the dangerous-command list contains one of the words in the input. Empty input, unbalanced quoting, NUL input, or another tokenization failure SHALL be rejected with reason `unparseable`. Rejection SHALL occur before policy confirmation or process creation.

#### Scenario: Quoted argument remains one simple action

- **WHEN** a supported command contains balanced quoting for an argument with spaces and no shell control syntax
- **THEN** analysis accepts one action whose argument preserves the embedded spaces

#### Scenario: Compound command is rejected

- **WHEN** input contains an additional command separated by `;`, `&&`, `||`, a pipeline, or a newline
- **THEN** analysis rejects it with `rejection_reason` set to `shell_metachar`

#### Scenario: Command substitution is rejected

- **WHEN** input contains backtick substitution or a form such as `$(touch marker)`
- **THEN** analysis rejects it with `rejection_reason` set to `shell_metachar`

#### Scenario: Unbalanced quoting is rejected

- **WHEN** input cannot be tokenized because a quote is not closed
- **THEN** analysis rejects it with `rejection_reason` set to `unparseable`

### Requirement: Security decisions use one canonical action

For an accepted command, classification, project-policy evaluation, confirmation, path-operand validation, and execution SHALL refer to the same canonical executable and ordered argument vector. The system SHALL NOT authorize one textual action and execute a different action produced by later shell interpretation.

#### Scenario: Spacing and quoting cannot change the executed action

- **WHEN** a supported command with quoted or escaped spaces passes all security gates
- **THEN** the executable and ordered arguments presented to those gates are the same executable and ordered arguments submitted for execution

#### Scenario: Ambiguous action is not authorized

- **WHEN** the system cannot derive one unambiguous canonical executable and argument vector
- **THEN** it rejects the input before policy confirmation or process creation

### Requirement: Confirmation modes

The system SHALL provide confirmation modes of exactly: `ask`, `auto`, `refuse`, and `compat`. The active mode SHALL be readable via a context-scoped confirmation policy. When no product policy is installed, the default mode SHALL be `compat`.

#### Scenario: Default mode is compat

- **WHEN** no confirmation policy has been installed for the current context
- **THEN** the effective confirmation mode is `compat`

#### Scenario: Auto mode allows without prompting

- **WHEN** the active mode is `auto` and confirmation is required for an action
- **THEN** the gate allows the action without invoking an interactive prompt

#### Scenario: Refuse mode denies without prompting

- **WHEN** the active mode is `refuse` and confirmation is required for an action
- **THEN** the gate denies the action without invoking an interactive prompt

### Requirement: Interactive confirmation prompt

When the active mode is `ask` and confirmation is required, the system SHALL prompt the user with a Rich yes/no confirmation defaulting to No. Affirmative answers SHALL allow the action; negative or default answers SHALL deny the action. The prompt function SHALL be injectable for tests.

#### Scenario: Ask mode approves on yes

- **WHEN** mode is `ask` and the confirm function returns True
- **THEN** the confirmation gate allows the action and records outcome `approved`

#### Scenario: Ask mode denies on no

- **WHEN** mode is `ask` and the confirm function returns False
- **THEN** the confirmation gate denies the action and records outcome `denied`

### Requirement: Compat mode preserves v0.6 library defaults

In `compat` mode, confirmation SHALL be required only for shell actions classified as `dangerous` (always denied without prompt). Shell `write` actions and filesystem mutate actions (`write_file`, `delete_file`) SHALL be allowed without prompting.

#### Scenario: Compat refuses dangerous without prompt

- **WHEN** mode is `compat` and a dangerous shell action requests confirmation
- **THEN** the gate denies without prompting

#### Scenario: Compat allows write without prompt

- **WHEN** mode is `compat` and a write shell or filesystem mutate action requests confirmation
- **THEN** the gate allows without prompting

### Requirement: Resolve product confirmation mode from CLI flags

The CLI SHALL resolve product confirmation mode as: `--yes` maps to `auto`; otherwise if stdin is a TTY map to `ask`; otherwise map to `refuse`.

#### Scenario: --yes selects auto

- **WHEN** `council run` is invoked with `--yes`
- **THEN** the resolved confirmation mode is `auto`

#### Scenario: Non-TTY without --yes selects refuse

- **WHEN** `council run` is invoked without `--yes` and stdin is not a TTY
- **THEN** the resolved confirmation mode is `refuse`

### Requirement: Structured audit log records

The system SHALL support appending structured audit records for tool invocations. Each record SHALL include: a UTC timestamp, tool name, arguments, success boolean, optional error message, metadata (JSON-serializable), and optional session id identifying the caller run. When no audit logger is installed for the current context, recording SHALL be a no-op.

#### Scenario: Record includes required fields

- **WHEN** an audit logger is installed and a tool invocation is recorded
- **THEN** the appended record includes timestamp, tool name, arguments, success, and session id when available

#### Scenario: No logger is a no-op

- **WHEN** no audit logger is installed and a record is requested
- **THEN** no file is written and no error is raised

### Requirement: Append-only audit storage under .council

When sandbox is initialized, audit events SHALL be stored as append-only JSON Lines under `.council/audit/` (default file `events.jsonl`) within the project root. Existing lines SHALL NOT be rewritten by normal append operations.

#### Scenario: Events append to JSONL file

- **WHEN** multiple tool invocations are audited for an initialized sandbox
- **THEN** each event is appended as one JSON object line in `.council/audit/events.jsonl`

#### Scenario: Prior events remain intact

- **WHEN** a new audit event is appended after prior events exist
- **THEN** previously written lines remain unchanged

### Requirement: Argument truncation in audit records

String argument values that exceed a fixed size limit SHALL be truncated in the stored audit record with an explicit truncation marker. Truncation SHALL NOT change the actual tool execution arguments.

#### Scenario: Large string arg truncated in audit only

- **WHEN** a tool is invoked with a string argument larger than the audit size limit
- **THEN** the audit record stores a truncated value with a truncation marker while the tool still receives the full argument

### Requirement: council audit show

The CLI SHALL provide `council audit show` that displays recent audit events from the project audit log (newest or file order with a configurable limit). It SHALL support filtering by session id and a `--workspace` root override. When the audit log is missing or empty, the command SHALL report that there are no events without crashing.

#### Scenario: Show recent events

- **WHEN** `council audit show` is run for a project with existing audit events
- **THEN** the CLI displays audit entries including timestamp, tool name, success, and session id

#### Scenario: Empty audit log

- **WHEN** `council audit show` is run and no audit events exist
- **THEN** the CLI reports that there are no events and exits successfully

### Requirement: council audit export

The CLI SHALL provide `council audit export` that writes audit events to a user-specified output path. Export SHALL support optional session filtering. The default export format SHALL be JSON Lines.

#### Scenario: Export all events as JSONL

- **WHEN** `council audit export` is run with an output path and events exist
- **THEN** the output file contains one JSON object per line for each exported event

#### Scenario: Export filtered by session

- **WHEN** `council audit export` is run with a session filter
- **THEN** only events matching that session id are written to the output file

### Requirement: Policy file schema and validation

The system SHALL support an optional project-root policy file named `council.policy.yaml` whose structure is validated before use. Valid fields for this milestone SHALL include `allowed_commands` (list of patterns), `denied_commands` (list of patterns), and `denied_paths` (list of path patterns). Invalid structure SHALL cause a clear validation error and SHALL NOT silently apply a partial policy. When the file is absent, the system SHALL use built-in defaults without requiring a policy file.

#### Scenario: Valid policy loads successfully

- **WHEN** `council.policy.yaml` contains valid `allowed_commands`, `denied_commands`, and/or `denied_paths` lists
- **THEN** the policy is accepted and available for evaluation

#### Scenario: Invalid policy is rejected

- **WHEN** `council.policy.yaml` has an invalid type for a known field (for example `denied_commands` is a string instead of a list)
- **THEN** loading fails with a validation error and the invalid file is not applied

#### Scenario: Missing policy uses defaults

- **WHEN** no `council.policy.yaml` exists at the project root
- **THEN** the system continues with built-in defaults and does not error solely due to the missing file

### Requirement: Denied command patterns hard-block

When a non-empty `denied_commands` list is active, any shell command that matches a denied pattern SHALL be refused before execution. Refusal SHALL return a structured tool failure (not an uncaught exception) indicating policy denial.

#### Scenario: Denied command is refused

- **WHEN** the active policy denies a pattern such as `curl *` and `run_command` is invoked with `curl https://example.com`
- **THEN** the command is not executed and the tool result indicates policy denial

### Requirement: Allowed command list restricts shell commands

When `allowed_commands` is present and non-empty, a shell command SHALL be allowed by policy only if it matches at least one allowed pattern. Commands that fail the allowlist SHALL be refused before execution even if they would otherwise be classified as `read`. When `allowed_commands` is absent or empty, no allowlist restriction SHALL be applied by the policy layer.

#### Scenario: Command outside allowlist is refused

- **WHEN** the active policy sets `allowed_commands` to patterns such as `pytest *` and `run_command` is invoked with `echo hello`
- **THEN** the command is not executed and the tool result indicates the command is not allowed by policy

#### Scenario: Command matching allowlist proceeds to later gates

- **WHEN** the active policy allows `echo *` and `run_command` is invoked with `echo hello`
- **THEN** the policy allowlist check passes and later classification/confirmation gates still apply

#### Scenario: Empty allowlist means no allowlist restriction

- **WHEN** the active policy omits `allowed_commands` or sets it to an empty list
- **THEN** shell commands are not refused solely for failing an allowlist

### Requirement: Policy evaluation order for shell commands

For shell commands, policy evaluation SHALL apply `denied_commands` before `allowed_commands`. A command matching a denied pattern SHALL be refused even if it also matches an allowed pattern.

#### Scenario: Deny wins over allow

- **WHEN** a command matches both a denied pattern and an allowed pattern
- **THEN** the command is refused as denied by policy

### Requirement: Context-scoped active policy

The system SHALL expose a context-scoped active policy for tool and guard evaluation. When no policy is installed, evaluation SHALL behave as built-in defaults (no extra command denials/allowlist; no extra denied paths from policy). Installing and resetting the active policy SHALL be possible for the duration of a product run.

#### Scenario: No installed policy uses built-in defaults

- **WHEN** no product policy is installed in the current context
- **THEN** command policy checks impose no extra deny/allow list beyond built-in classifier/confirmation behavior

#### Scenario: Installed policy is visible to evaluators

- **WHEN** a valid policy is installed for the current context
- **THEN** subsequent command and path evaluations use that policy until it is reset
