# Security

## Purpose

Fail-closed command analysis, interactive confirmation gates, structured audit logging, and project policy files for shell and filesystem tools. Introduced in v0.6 (classification), v0.7 (confirmation), v0.8 (audit), and v0.9 (policy), with simple-command containment hardened in v0.9.1; later milestones add trust tiers.

## Requirements

### Requirement: One mandatory policy dispatcher for product tool calls

Every product invocation of a filesystem or shell tool SHALL enter one dispatcher before any tool operation is performed. The dispatcher SHALL use one action identity to validate context, enforce the tool-call limit, obtain the tool-specific security decision, track the result, persist optional session evidence, emit optional durable audit evidence, and return the result. CLI, CrewAI, escalation, and supported library product paths SHALL NOT expose a second executable tool path.

#### Scenario: Same action has one product decision path

- **WHEN** the same canonical tool name and arguments are invoked through a supported library entry point and through a CrewAI adapter under equivalent contexts
- **THEN** both invocations pass through the dispatcher and produce equivalent allow or deny decisions and reason metadata

#### Scenario: Direct public tool call cannot bypass dispatcher

- **WHEN** a caller imports a public filesystem or shell tool function directly
- **THEN** the function delegates to the dispatcher rather than executing a raw operation

#### Scenario: Unknown tool is denied

- **WHEN** the dispatcher receives a tool name outside the registered product tool set
- **THEN** it returns a structured denial and performs no filesystem operation or subprocess execution

### Requirement: Security context is one validated snapshot

Each dispatched action SHALL use exactly one immutable security-context snapshot containing a non-empty request identifier, optional session identifier, workspace guard/root, validated project-policy snapshot and its recognized schema-version label, confirmation policy, tool-call tracker, optional session writer, and optional audit logger. Context validation SHALL reject inconsistent workspace/session, session/audit, or policy/schema-label state before the tool-specific operation runs. Reserved fields for future authorization work SHALL NOT grant principal, authentication, grant, or Trust Tier semantics in this milestone.

#### Scenario: Valid context supplies one action snapshot

- **WHEN** a valid context is active and a tool is invoked
- **THEN** workspace, project policy, policy schema label, confirmation behavior, request/session correlation, and call limit for that invocation all come from that same context object

#### Scenario: Context identity mismatch fails closed

- **WHEN** a context's session workspace or audit session identity does not match the context workspace/session
- **THEN** context installation or invocation is rejected before a tool operation starts

#### Scenario: Versioned policy supplies snapshot label

- **WHEN** a context contains a validated project policy with supported `schema_version: 1`
- **THEN** its policy-version label identifies project-policy schema version 1 for middleware result and audit correlation

#### Scenario: Policy label does not create a versioned schema

- **WHEN** a caller attempts to pair an arbitrary or legacy policy-version label with an absent or mismatched policy snapshot
- **THEN** context validation rejects the mismatch because a label alone cannot validate or create a project-policy schema

#### Scenario: Missing project policy uses built-in label

- **WHEN** a context has no project policy file and uses built-in defaults
- **THEN** its policy-version label identifies the built-in policy state rather than an unversioned project schema

### Requirement: Security context lifecycle fails closed

A product scope SHALL install and clean up its security context through one lifecycle operation. A missing context, a context that was already closed, or a stale context retained after cleanup SHALL be denied with a structured diagnostic result. No default product context SHALL be synthesized by a public tool function.

#### Scenario: Missing context is denied

- **WHEN** a public product tool is called without an installed security context
- **THEN** it returns `success=False` with a stable `security_context_missing` rejection reason and performs no operation

#### Scenario: Cleanup prevents later use

- **WHEN** a product scope exits and cleans up its security context
- **THEN** a later tool call in that scope fails closed instead of retaining policy, confirmation, tracker, session, or audit state

#### Scenario: Stale copied context is denied

- **WHEN** an execution context copied while a security context was active attempts a tool call after the owning lifecycle has closed
- **THEN** the call is rejected as a closed security context and performs no operation

### Requirement: Middleware evidence correlates attempts and results

When durable audit storage is present in the security context, the dispatcher SHALL emit an attempt record before an accepted tool operation and a result record after completion or refusal. Both records SHALL carry the same request and action identifiers, tool name, and session identifier when present. Policy denial, confirmation denial, tool-limit denial, expected tool failure, unexpected execution failure, and success SHALL all produce correlated result evidence. This correlation is not an audit hash chain or integrity guarantee.

#### Scenario: Successful action has correlated audit phases

- **WHEN** a dispatched tool succeeds with durable audit storage configured
- **THEN** its attempt and result audit records share one request/action correlation and the result records an allow decision

#### Scenario: Policy denial is audited by middleware

- **WHEN** a shell action is denied by project policy with durable audit storage configured
- **THEN** middleware records a correlated denied result and no subprocess starts

#### Scenario: Tool limit denial is audited by middleware

- **WHEN** a tool call is attempted after the context tracker reaches its limit
- **THEN** middleware records the limit-denied attempt/result correlation and does not invoke the tool operation

#### Scenario: No sandbox has no durable audit file

- **WHEN** a product run has no initialized sandbox and therefore its context has no audit logger or session writer
- **THEN** the dispatcher still returns request/action/decision metadata and records allowed calls in the in-memory tracker, but creates no durable audit or session file

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

The system SHALL support appending structured audit records for dispatched tool invocations. Each middleware-owned record SHALL include: a UTC timestamp, phase (`attempt` or `result`), tool name, arguments, optional success boolean, optional error message, metadata (JSON-serializable), request id, action id, decision when known, and optional session id identifying the caller run. Existing non-tool administrative audit callers MAY emit a single `result` record. When no audit logger is installed for the current security context, durable recording SHALL be a no-op.

#### Scenario: Record includes required fields

- **WHEN** an audit logger is installed and a dispatched tool invocation completes or is denied
- **THEN** the appended result record includes timestamp, phase, tool name, arguments, success, request id, action id, decision, and session id when available

#### Scenario: Attempt and result correlate

- **WHEN** middleware records both phases of one invocation
- **THEN** the records have the same request id, action id, tool, arguments, and optional session id

#### Scenario: No logger is a no-op

- **WHEN** no audit logger is present in the active security context
- **THEN** no audit file is written and no audit-storage error is raised

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

### Requirement: Project policy trust boundary is restrict-only

The project-root `council.policy.yaml` SHALL be treated as an untrusted, project-owned restriction source, not as user authorization. Its command allowlist SHALL only narrow actions admitted by built-in analysis and later security gates; its command and path denylists SHALL only add denials. Project policy SHALL NOT remove a built-in denial or grant principal scope, authentication, trust grants, Trust Tier, confirmation bypass, or another elevation of authority.

#### Scenario: Command allowlist cannot authorize unsupported action

- **WHEN** project policy lists a command pattern that would match an action rejected by built-in command analysis
- **THEN** the action remains rejected and project policy does not turn it into an accepted or authorized action

#### Scenario: Project policy cannot remove built-in path denial

- **WHEN** a valid project policy omits a built-in sensitive path or supplies only unrelated path restrictions
- **THEN** the built-in sensitive path remains denied

#### Scenario: Authorization-shaped field is rejected

- **WHEN** project policy contains a scope, authentication, grant, Trust Tier, confirmation-bypass, or other unsupported authorization field
- **THEN** the entire policy is rejected as an unknown field before use and no authority is granted

#### Scenario: User-owned trust data remains a separate boundary

- **WHEN** a caller needs persistent user authorization or a revocable trust grant
- **THEN** project policy is not used as that store and this version provides no project-policy field that can create such authorization

### Requirement: Policy file schema and validation

The system SHALL support an optional project-root policy file named `council.policy.yaml` with required integer `schema_version: 1`. The only project-policy fields supported by schema version 1 SHALL be `schema_version`, `allowed_commands` (list of string patterns), `denied_commands` (list of string patterns), and `denied_paths` (list of string path patterns). Missing or unsupported versions, unknown or misspelled fields, invalid field types, and malformed YAML SHALL reject the entire file before use without silently applying any subset. Validation diagnostics SHALL identify the file, schema-version problem when applicable, and offending field without echoing secret field values. When the file is absent, the system SHALL use built-in defaults without requiring a policy file.

#### Scenario: Valid policy loads successfully

- **WHEN** `council.policy.yaml` declares integer `schema_version: 1` and contains only valid version 1 restriction fields
- **THEN** the complete policy is accepted and available as a schema-versioned restriction snapshot

#### Scenario: Unversioned legacy policy is rejected

- **WHEN** an existing v0.9 policy file omits `schema_version`
- **THEN** loading fails with a migration diagnostic requiring `schema_version: 1` and no policy fields are applied

#### Scenario: Unsupported policy version is rejected

- **WHEN** `council.policy.yaml` declares a schema version other than integer 1
- **THEN** loading fails with a diagnostic identifying the unsupported version and the supported version

#### Scenario: Unknown field is rejected

- **WHEN** a version 1 policy contains any unrecognized field
- **THEN** loading fails with a diagnostic identifying that field and no recognized fields are partially applied

#### Scenario: Misspelled security field is rejected

- **WHEN** a version 1 policy contains a misspelling such as `denied_command`
- **THEN** loading fails instead of silently omitting the intended restriction

#### Scenario: Secret value is not echoed in validation error

- **WHEN** an unsupported authorization-shaped field contains a secret-looking value
- **THEN** the validation error identifies the field but does not contain its value

#### Scenario: Invalid policy is rejected

- **WHEN** a version 1 policy gives a known field an invalid type
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

When `allowed_commands` is present and non-empty, a shell command SHALL pass the project-policy layer only if it matches at least one allowed pattern. Matching SHALL NOT override built-in command-analysis rejection, a command or path denial, confirmation policy, or any later authorization gate. Commands that fail the allowlist SHALL be refused before execution even if they would otherwise be classified as `read`. When `allowed_commands` is absent or empty, no allowlist restriction SHALL be added by the project-policy layer.

#### Scenario: Command outside allowlist is refused

- **WHEN** the active policy sets `allowed_commands` to patterns such as `pytest *` and `run_command` is invoked with `echo hello`
- **THEN** the command is not executed and the tool result indicates the command is not allowed by policy

#### Scenario: Command matching allowlist proceeds to later gates

- **WHEN** the active policy allows `echo *` and `run_command` is invoked with `echo hello`
- **THEN** the project-policy filter passes while built-in analysis and later confirmation or authorization gates still decide whether execution may occur

#### Scenario: Allowed pattern does not elevate dangerous action

- **WHEN** a dangerous action matches `allowed_commands` but later requires and fails confirmation
- **THEN** the action remains denied and no subprocess starts

#### Scenario: Empty allowlist means no allowlist restriction

- **WHEN** the active policy omits `allowed_commands` or sets it to an empty list
- **THEN** shell commands are not refused solely for failing a project-policy allowlist, while all built-in and later gates remain in force

### Requirement: Policy evaluation order for shell commands

For shell commands, policy evaluation SHALL apply `denied_commands` before `allowed_commands`. A command matching a denied pattern SHALL be refused even if it also matches an allowed pattern.

#### Scenario: Deny wins over allow

- **WHEN** a command matches both a denied pattern and an allowed pattern
- **THEN** the command is refused as denied by policy

### Requirement: Context-scoped active policy

The project policy used by product tool and guard evaluation SHALL be the policy snapshot stored in the active security context. A valid context whose policy value is absent SHALL apply built-in defaults (no extra command denials/allowlist and no extra denied paths from project policy). Installing and resetting the security context SHALL install and reset that policy snapshot together with the workspace, confirmation, tracker, session, and audit state.

#### Scenario: No installed policy uses built-in defaults

- **WHEN** an active valid security context contains no project policy
- **THEN** command policy checks impose no extra deny/allow list beyond built-in classifier and confirmation behavior

#### Scenario: Installed policy is visible to evaluators

- **WHEN** a valid context contains a loaded project policy
- **THEN** command and path evaluations for each dispatched action use that snapshot until the context is cleaned up

#### Scenario: Missing context does not use policy defaults

- **WHEN** no security context is installed
- **THEN** public tool invocation is denied rather than proceeding with an ambient default policy
