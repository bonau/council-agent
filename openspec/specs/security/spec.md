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

Each dispatched action SHALL use exactly one immutable security-context snapshot containing a non-empty request identifier, optional session identifier, workspace guard/root, validated project-policy snapshot and its recognized schema-version label, confirmation policy, tool-call tracker, optional session writer, optional audit logger, and one expected Council principal identity with a current-authority resolver. Context validation SHALL reject inconsistent workspace/session, session/audit, policy/schema-label, or principal-binding state before the tool-specific operation runs. The principal binding SHALL NOT represent session authentication, a trust grant, or Trust Tier state.

#### Scenario: Valid context supplies one action snapshot

- **WHEN** a valid context is active and a tool is invoked
- **THEN** workspace, project policy, policy schema label, confirmation behavior, request/session correlation, expected principal identity, and call limit for that invocation all come from that same context object

#### Scenario: Context identity mismatch fails closed

- **WHEN** a context's session workspace, audit session identity, or resolved principal identity does not match the context's bound workspace, session, or expected principal
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

### Requirement: Council principals are distinct from provider credentials

A Council authorization principal SHALL have a non-empty stable identifier, recognized principal kind, non-empty issuer/source, and an explicit set of recognized Council scopes. The OpenRouter API key SHALL be represented and loaded only as a model-provider credential and SHALL NOT be accepted as a Council principal, principal identifier, scope source, authentication proof, trust grant, or audit identity.

#### Scenario: Provider key cannot authorize a tool

- **WHEN** a caller supplies an OpenRouter provider credential but omits the Council principal
- **THEN** model credential handling remains separate and every dispatched tool action fails closed for missing principal

#### Scenario: Invalid principal is rejected

- **WHEN** a principal has an empty identifier or issuer, an unknown kind, or an unknown scope
- **THEN** it is rejected before any tool action executes

#### Scenario: Stable principal identity is preserved

- **WHEN** the same issuer, kind, and principal identifier is used across multiple decisions
- **THEN** those decisions have the same stable masked principal reference without exposing the raw identifier

### Requirement: Principal scopes are explicit and fail closed

The recognized Council scope set SHALL include exactly defined values for read, filesystem mutation, test execution, shell execution, and high-risk management. Before any registered product tool operation, the dispatcher SHALL resolve the current principal and require every scope assigned to the canonical top-level action. Missing, invalid, identity-mismatched, or insufficient authority SHALL return a structured denial with stable reason metadata and SHALL NOT be overridden by project policy, confirmation mode, `--yes`, wrappers, or composite-tool internals.

#### Scenario: Missing principal is denied

- **WHEN** a valid security context has no current Council principal
- **THEN** the action is denied with reason `principal_missing` before the handler, filesystem, or subprocess runs

#### Scenario: Unknown scope fails closed

- **WHEN** current principal authority contains a scope outside the recognized scope set
- **THEN** the action is denied as an invalid principal and no operation starts

#### Scenario: Insufficient scope is denied

- **WHEN** a valid principal lacks one or more scopes required by the requested action
- **THEN** the action is denied with reason `scope_insufficient` and reports masked principal, required, granted, and missing scopes

#### Scenario: Confirmation cannot elevate scope

- **WHEN** a principal lacks a required scope while confirmation mode is `auto` or an interactive confirmation would approve
- **THEN** the dispatcher denies before confirmation and does not elevate the principal

### Requirement: Current principal authority is evaluated per action

Every dispatched action SHALL resolve current principal authority again and SHALL compare its issuer, kind, and stable identifier to the identity bound into the security context. Scope reductions SHALL affect the next action. An absent current principal SHALL be treated as revoked for that decision, and a substituted identity SHALL fail closed. This per-action resolution SHALL NOT provide a persistent grant store or session authentication.

#### Scenario: Scope tightening applies immediately

- **WHEN** a principal source returns fewer scopes after one allowed action
- **THEN** the next action uses the reduced scope set and is denied if its required scope was removed

#### Scenario: Revocation applies immediately

- **WHEN** a principal source returns no current principal after one allowed action
- **THEN** the next action is denied with reason `principal_revoked` and does not use the prior principal snapshot

#### Scenario: Principal substitution is denied

- **WHEN** a current-principal source returns a different issuer, kind, or stable identifier from the context-bound identity
- **THEN** the action is denied with reason `principal_mismatch`

### Requirement: Audit evidence records masked scope decisions

Middleware attempt and result evidence SHALL include a recursively sanitized authorization decision containing a masked stable principal reference when available, recognized principal kind, required scopes, granted scopes, missing scopes, allow/deny outcome, and stable authorization reason. Raw provider credentials, Council credentials, and raw principal identifiers SHALL NOT be persisted in audit or session evidence.

#### Scenario: Allowed decision is auditable

- **WHEN** a scoped principal is allowed to execute an action with durable audit enabled
- **THEN** the correlated attempt and result contain the same masked principal reference and allowed scope decision

#### Scenario: Denied decision is auditable

- **WHEN** scope authorization denies an action with durable audit enabled
- **THEN** the correlated attempt and result contain a denied scope decision and stable reason without invoking the operation

#### Scenario: Credential and raw identity are not persisted

- **WHEN** provider credential text or a secret-looking raw principal identifier is present in runtime inputs
- **THEN** neither value appears in stored audit or session evidence

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

When durable audit storage is present in the security context, the dispatcher SHALL emit an attempt record before an accepted tool operation and a result record after completion or refusal. Both records SHALL carry the same request and action identifiers, tool name, arguments, and session identifier when present. The result SHALL additionally reference the exact deterministic event ID of its preceding attempt. Policy denial, confirmation denial, tool-limit denial, expected tool failure, unexpected execution failure, and success SHALL all produce a structurally valid correlated result or fail closed when the attempt cannot be durably recorded. This correlation and per-event identity are an integrity substrate, not a complete audit hash chain or external tamper-proof guarantee.

#### Scenario: Successful action has correlated audit phases

- **WHEN** a dispatched tool succeeds with durable audit storage configured
- **THEN** its attempt and result audit records share one request/action correlation, the result references the attempt event ID, and the result records an allow decision

#### Scenario: Policy denial is audited by middleware

- **WHEN** a shell action is denied by project policy with durable audit storage configured
- **THEN** middleware records a correlated denied result referencing the exact attempt and no subprocess starts

#### Scenario: Tool limit denial is audited by middleware

- **WHEN** a tool call is attempted after the context tracker reaches its limit
- **THEN** middleware records the limit-denied attempt/result correlation with an exact attempt reference and does not invoke the tool operation

#### Scenario: Broken result reference is detected

- **WHEN** a versioned result references a missing attempt or one with different request, action, tool, or session correlation
- **THEN** audit integrity validation fails explicitly

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

String values that exceed a fixed size limit SHALL be truncated in stored audit and session evidence with an explicit truncation marker. Recursive secret redaction SHALL occur before truncation so truncation cannot leave a secret prefix on disk. Sanitization and truncation SHALL NOT change actual tool execution arguments or returned tool results.

#### Scenario: Large string arg truncated in audit only

- **WHEN** a tool is invoked with a non-secret string argument larger than the audit size limit
- **THEN** the audit record stores a truncated value with a truncation marker while the tool still receives the full argument

#### Scenario: Large secret is redacted before truncation

- **WHEN** a value contains a recognized secret longer than the storage limit
- **THEN** persisted evidence contains the redaction marker and no retained prefix of the secret

### Requirement: Persisted evidence is recursively redacted

Before audit or session evidence is written, the system SHALL recursively sanitize arguments, metadata, output, error, prompt, and nested collection values. Sensitive field names and common secret content forms, including API keys, bearer tokens, JWTs, provider-token prefixes, credential assignments, passphrases, and private-key blocks, SHALL be replaced with an explicit redaction marker before length truncation. Display and export SHALL use sanitized values, including for readable legacy records.

#### Scenario: Sensitive field is fully masked

- **WHEN** a nested audit or session value is stored under a recognized sensitive field name
- **THEN** the persisted value is the redaction marker and no substring of the original secret is written

#### Scenario: Secret embedded in ordinary text is masked

- **WHEN** an argument, output, metadata value, or error contains a recognized bearer token, JWT, provider token, credential assignment, or private-key block without a sensitive field name
- **THEN** the recognized secret substring is replaced before the text is truncated or persisted

#### Scenario: Non-secret values remain useful

- **WHEN** persisted evidence contains ordinary paths, status values, counts, and messages that match no secret rule
- **THEN** those values remain available subject only to the existing size limit

#### Scenario: Legacy export is sanitized

- **WHEN** a legacy event contains an unredacted recognized secret and is shown or exported
- **THEN** the command emits the masked value and identifies the legacy evidence as unverified

### Requirement: Audit events use a versioned canonical integrity envelope

Each newly persisted audit event SHALL contain a supported schema version, a strictly increasing positive sequence number, and a deterministic event ID derived from the canonical JSON representation of all stored event fields except that ID. Sequence allocation and append SHALL be serialized across writers for one log before an event is committed. The canonical per-event identity SHALL be a substrate for later chaining and SHALL NOT be represented as an externally anchored hash chain.

#### Scenario: New events receive contiguous sequence and stable identity

- **WHEN** multiple supported writers append events to one valid audit log
- **THEN** committed events have contiguous sequence numbers and each event ID remains identical after reload and canonical re-encoding

#### Scenario: Event content change is detected

- **WHEN** a stored field covered by the canonical envelope is changed without its original event ID remaining valid
- **THEN** integrity validation fails with a sanitized explicit error rather than returning the event as valid

#### Scenario: Gap duplicate or reorder is detected

- **WHEN** versioned events contain a missing, repeated, or out-of-order sequence
- **THEN** integrity validation fails and does not treat the affected file as normal empty history

#### Scenario: Partial line is detected

- **WHEN** an audit file ends with an incomplete JSON object, lacks the committed line terminator, or contains a malformed or blank record line
- **THEN** integrity validation fails with a line-oriented sanitized error

#### Scenario: Legacy envelope is explicit

- **WHEN** a pre-envelope audit record is loaded successfully
- **THEN** it remains readable in sanitized form but integrity status is `legacy_unverified` rather than `verified`

### Requirement: Audit integrity status is visible

Audit loading SHALL return an integrity status of `empty`, `verified`, or `legacy_unverified` for valid input and SHALL raise a typed integrity error for malformed or inconsistent input. `council audit show` and `council audit export` SHALL display the valid status and SHALL exit unsuccessfully with a sanitized diagnostic when validation fails.

#### Scenario: Show reports verified history

- **WHEN** `council audit show` reads only valid versioned events
- **THEN** its output identifies the history as `verified`

#### Scenario: Export reports legacy history

- **WHEN** `council audit export` reads one or more legacy events without a structural error
- **THEN** its output identifies the export as `legacy_unverified` and writes sanitized records

#### Scenario: Invalid history is not exported

- **WHEN** audit validation detects an invalid event, gap, duplicate, partial line, or broken attempt/result reference
- **THEN** show or export exits unsuccessfully and export does not represent the history as valid

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

### Requirement: Session authentication state is independently bound

Authentication state SHALL be distinct from a request identifier, session UUID, Council principal declaration, provider credential, project policy, confirmation result, and trust grant. Every authentication challenge and step-up token SHALL be bound to the current masked principal identity, canonical workspace, non-empty runtime session identifier, declared authentication purpose, exact canonical top-level action, issue time, and expiry.

#### Scenario: Session identifier alone does not authenticate

- **WHEN** a high-privilege action has a valid session identifier and principal scope but no valid step-up authentication
- **THEN** the dispatcher denies the action before its handler and does not treat the session identifier as proof

#### Scenario: Wrong binding is denied

- **WHEN** a challenge or step-up token is presented for a different principal, workspace, session, purpose, tool, or arguments
- **THEN** authentication fails closed with a stable binding-mismatch reason and the action does not execute

#### Scenario: Provider credential does not authenticate

- **WHEN** an OpenRouter credential is available but no Council authentication verifier or proof is available
- **THEN** the provider credential is not used as step-up evidence

### Requirement: Challenges and step-up tokens are fresh and non-replayable

Authentication challenges and issued step-up tokens SHALL contain unpredictable values, SHALL have bounded lifetimes, and SHALL be consumable at most once. Challenge completion SHALL consume the challenge before credential comparison. Step-up evaluation SHALL consume the token before binding evaluation. Missing, unknown, expired, revoked, previously consumed, or insufficiently fresh evidence SHALL be denied with stable reason metadata. Restart SHALL invalidate all outstanding process-local challenges and tokens.

#### Scenario: Successful challenge creates one token

- **WHEN** a valid verifier response completes an unexpired challenge with matching binding
- **THEN** authentication succeeds and produces one opaque step-up token without persisting the verifier, response, challenge value, or token value

#### Scenario: Challenge replay is denied

- **WHEN** a completed or failed challenge is submitted again
- **THEN** completion is denied as replay and no additional step-up token is issued

#### Scenario: Token replay is denied

- **WHEN** a step-up token has already been evaluated once
- **THEN** a later evaluation is denied as replay even if the original evaluation was denied for a binding mismatch

#### Scenario: Expired or stale proof is denied

- **WHEN** a challenge or step-up token exceeds its absolute expiry or the high-privilege decision's freshness window
- **THEN** authentication is denied as expired before the action executes

#### Scenario: Revocation applies immediately

- **WHEN** the process-local authentication manager is revoked
- **THEN** outstanding challenges and tokens are rejected and no new challenge is issued by that manager

#### Scenario: Restart invalidates outstanding proof

- **WHEN** an opaque challenge or token from a prior manager instance is presented after process restart
- **THEN** the new manager rejects it as unknown rather than recovering authentication from the session UUID

### Requirement: High-privilege actions require fresh step-up

After principal scope authorization succeeds, a security context that explicitly requires high-risk step-up SHALL require every canonical action needing `high-risk:manage` to present a successful, matching, one-use proof within the configured freshness window before project confirmation or the tool handler. Product orchestration contexts SHALL enable this requirement. Direct library contexts MAY leave it disabled for backward compatibility or explicitly enable it. When required, authentication denial SHALL NOT be overridden by project policy, wrappers, confirmation mode, or `--yes`. Actions not requiring `high-risk:manage` SHALL NOT be elevated or otherwise changed by the presence of authentication state.

#### Scenario: Missing step-up denies high-risk action

- **WHEN** a principal has all scopes for a dangerous shell action, the context requires high-risk step-up, but it has no authentication manager or step-up provider
- **THEN** the action is denied with reason `authentication_missing` before confirmation or process creation

#### Scenario: Fresh step-up permits later gates

- **WHEN** a scoped high-risk action receives a fresh one-use proof matching its principal, workspace, session, purpose, and canonical action
- **THEN** the authentication gate passes and project policy, containment, and confirmation continue to decide the action

#### Scenario: Ordinary action remains scope-controlled

- **WHEN** an action does not require `high-risk:manage`
- **THEN** it continues through existing scope and lower security gates without requiring a step-up token

#### Scenario: Library compatibility is explicit

- **WHEN** a direct library context leaves the high-risk step-up requirement disabled
- **THEN** the dispatcher preserves its pre-v0.9.6 scope/policy/confirmation behavior and does not represent that context as authenticated

### Requirement: Authentication evidence is masked and auditable

Authentication success, failure, expiry, revocation, replay, and binding mismatch SHALL produce sanitized audit events when durable audit is configured. Authentication event and tool-decision evidence SHALL contain stable outcomes/reasons and only masked references for principal, workspace, action, challenge, and token. Raw verifier/passphrase values, challenge values, response values, opaque tokens, and provider credentials SHALL NOT be written to audit, session, console, policy, or release evidence.

#### Scenario: Lifecycle outcomes are auditable

- **WHEN** authentication succeeds, fails, expires, is revoked, or detects replay
- **THEN** the audit trail identifies the corresponding outcome and stable reason using masked correlation references

#### Scenario: Authentication secrets are absent from persistence

- **WHEN** verifier, response, challenge, and token values are exercised during a sandboxed run
- **THEN** raw audit JSONL, session metadata, session tool logs, console output, and evidence documents contain none of those values

#### Scenario: Tool evidence carries normalized decision

- **WHEN** a high-risk dispatcher decision is attempted
- **THEN** its correlated tool attempt/result metadata records the matching masked authentication decision or denial reason

### Requirement: Trust grants use a user-owned store outside the workspace
Persistent trust grants SHALL be loaded only from a canonical user-data location outside the active workspace. Before creating, reading, locking, auditing, or replacing store data, the system SHALL verify that every existing store component is non-symlink user-owned state with no group or other access, and SHALL fail closed on unsupported ownership checks, permission errors, workspace overlap, unsafe ancestors, or path replacement.

#### Scenario: Secure user-owned store is accepted
- **WHEN** the grant root is outside the workspace, owned by the current user, and accessible only to that user
- **THEN** the system may initialize directories and files with restrictive user-only permissions

#### Scenario: Workspace-local store is refused
- **WHEN** a configured grant-store path resolves inside the active workspace
- **THEN** the system refuses the operation without creating, reading, or replacing grant state

#### Scenario: Ownership or permission validation fails closed
- **WHEN** the store root, state file, lock, audit path, or an existing path component has a different owner, unsafe permissions, is a symlink, or cannot be securely inspected
- **THEN** the entire requested operation is refused and no grant is adopted or changed

### Requirement: Grant records have exact canonical authority bindings
Each grant SHALL have a unique opaque ID and SHALL bind one masked Council principal identity, one recognized canonical top-level action, one canonical JSON resource object, a non-empty closed set of Council scopes, the masked creating principal, a timezone-aware creation timestamp, and an optional later expiry. Canonicalization SHALL reject unknown actions, non-object or non-finite resources, unrecognized scopes, naive timestamps, wildcard authority, and a grant scope not already held by the subject and creator.

#### Scenario: Exact grant is persisted
- **WHEN** an authenticated principal creates a grant for itself using a recognized action, exact resource object, and a subset of its current scopes
- **THEN** the stored record contains the exact canonical bindings, creator, timestamps, and one new unique ID

#### Scenario: Grant cannot expand current scope
- **WHEN** a requested grant contains a scope that the current principal does not hold
- **THEN** creation is denied before persistent state changes

#### Scenario: Semantically equal resources have one canonical form
- **WHEN** equivalent resource objects differ only in key ordering or insignificant JSON whitespace
- **THEN** they resolve to the same canonical resource and cannot create conflicting live grants

### Requirement: Trust grant administration requires fresh authentication
Grant, revoke, and list operations SHALL require a current Council principal with the operation's required scope and fresh one-use authentication bound to that principal, the canonical store, a non-empty management session, the exact operation, and its canonical arguments. Grant and revoke SHALL require `high-risk:manage`; list SHALL require `read`. Session IDs, provider credentials, project policy, confirmation, `ConfirmMode.AUTO`, `--yes`, and Agent workspace writes SHALL NOT satisfy authentication, create a grant, restore a revoked grant, or expand grant scope.

#### Scenario: Missing authentication cannot create state
- **WHEN** a fully scoped principal requests a grant without fresh management authentication
- **THEN** creation is denied and the store remains unchanged

#### Scenario: Authentication is exact-operation bound
- **WHEN** authentication issued for list, a different grant target, another store, another principal, or another session is presented to grant or revoke
- **THEN** the operation is denied without changing state

#### Scenario: Project-controlled input cannot grant authority
- **WHEN** project policy, workspace files, confirmation auto mode, or `--yes` requests broader or restored authority
- **THEN** no grant-store administration authentication is created and no grant changes

### Requirement: Invalid and inactive grant state is never adopted
The store SHALL use one strict integer schema version and SHALL reject the complete document on malformed encoding or JSON, unknown fields, unknown or non-integer schema, invalid records, duplicate IDs, duplicate or conflicting live bindings, or inconsistent revocation data. Revoked grants SHALL become inactive immediately for the next locked lookup and across process restart. Expired grants SHALL be inactive at expiry, and clock rollback or invalid time relationships SHALL fail closed.

#### Scenario: Revoke applies to the next lookup
- **WHEN** an authenticated principal revokes an active grant
- **THEN** the same grant is inactive for the next lookup and remains inactive after reopening the store

#### Scenario: Expired grant is ignored
- **WHEN** current UTC time is at or after a grant's expiry
- **THEN** lookup and active listing do not adopt the grant

#### Scenario: Corrupt or future state fails closed
- **WHEN** the store contains malformed data, duplicate/conflicting records, unknown fields, or an unsupported schema version
- **THEN** list, lookup, grant, and revoke refuse the whole store rather than using a partial or legacy interpretation

### Requirement: Grant mutations are atomic and serialized
Every grant or revoke mutation SHALL take exclusive inter-process ownership of a validated user-owned lock, re-read and validate current state while locked, write a complete same-directory temporary file with user-only permissions, durably flush it, atomically replace the state file, and durably flush the containing directory. A failed write, flush, replace, lock, or post-replace validation SHALL be reported explicitly and SHALL never expose a partially written store as valid state.

#### Scenario: Concurrent grants preserve both updates
- **WHEN** two processes request valid non-conflicting grants concurrently
- **THEN** serialized read-modify-replace commits preserve both complete records without lost updates

#### Scenario: Interrupted replacement is not adopted
- **WHEN** temporary-file writing or replacement fails
- **THEN** a later read sees either the prior complete store or the new complete store, never a partial document

### Requirement: Trust grant decisions produce masked audit evidence
Every grant, revoke, list, and lookup decision SHALL emit correlated administrative evidence to the user-owned trust control plane before returning success. Evidence SHALL include the operation, allow or deny result, stable reason, management session or request correlation, grant ID reference when applicable, masked principal and creator references, canonical action reference, resource reference, and scope names, while excluding raw principal IDs, raw resources, authentication verifier/challenge/response/token values, and unmasked grant IDs.

#### Scenario: Successful management evidence is masked
- **WHEN** an authenticated grant or revoke operation succeeds
- **THEN** audit evidence correlates the decision using only masked identity, target, and grant references

#### Scenario: Refusal evidence is masked
- **WHEN** authentication, validation, expiry, conflict, ownership, or permission checks deny an operation after the audit boundary is safely available
- **THEN** a masked denial reason is recorded without credential or resource disclosure

### Requirement: Trust store recovery preserves fail-closed semantics
Backup and recovery guidance SHALL require offline user-controlled copying with user-only permissions, validation before replacement, no schema downgrade, and preservation of newer revocations. The implementation SHALL provide a validation-only operation that never repairs, migrates, truncates, or partially adopts invalid state automatically.

#### Scenario: Validation does not repair corruption
- **WHEN** an operator validates a corrupted or unsupported backup
- **THEN** validation reports refusal and leaves both active state and backup unchanged

#### Scenario: Schema downgrade is refused
- **WHEN** a store or backup declares an older unrecognized or future schema
- **THEN** it is refused without automatic downgrade or partial migration

### Requirement: Versioned trust decision matrix is the authority contract
The system SHALL expose one versioned, deterministic trust-decision contract whose complete input vector contains project-policy disposition, principal/scope disposition, authentication disposition, trust-grant disposition, canonical action risk, and interaction disposition. Its output SHALL be exactly `deny`, `require_confirmation`, or `allow`, with one stable reason code and a JSON-safe representation of every non-secret input dimension. Matrix version 1 SHALL evaluate denials in this order: policy, principal/scope, authentication, grant; only after those gates pass SHALL action risk and interaction affect the result.

#### Scenario: Policy denial has highest authority precedence
- **WHEN** a decision vector contains a policy denial together with any scope, authentication, grant, risk, or interaction values
- **THEN** the result is `deny` with the corresponding stable policy reason and no later dimension can replace it

#### Scenario: Scope denial precedes authentication grant and interaction
- **WHEN** policy passes but principal/scope is missing, invalid, revoked, mismatched, or insufficient
- **THEN** the result is `deny` with the corresponding stable scope reason regardless of authentication, grant, action risk, confirmation approval, or automatic interaction

#### Scenario: Authentication denial precedes grant and interaction
- **WHEN** policy and scope pass but required authentication is missing, invalid, failed, expired, revoked, replayed, binding-mismatched, or unavailable because of a provider error
- **THEN** the result is `deny` with the corresponding stable authentication reason regardless of grant or interaction

#### Scenario: Invalid grant cannot be overridden
- **WHEN** policy, scope, and authentication pass but a required grant is missing, invalid, revoked, expired, or insufficient
- **THEN** the result is `deny` with the corresponding stable grant reason regardless of action risk or interaction mode

#### Scenario: Risk determines whether interaction is needed
- **WHEN** all authority gates pass and an action's risk requires confirmation but no confirmation outcome exists
- **THEN** the result is `require_confirmation` with reason `confirmation_required`

#### Scenario: Passed authority and resolved interaction allow
- **WHEN** all authority gates pass and the action either needs no interaction or has a permitted automatic, compatibility, or explicit approval outcome
- **THEN** the result is `allow` with reason `decision_allowed`

### Requirement: Confirmation is interaction only
Confirmation mode and confirmation outcomes SHALL control only how a decision that reached the interaction stage is resolved. They SHALL NOT create, select, restore, satisfy, or expand a principal, scope, authentication proof, trust grant, or project-policy permission. `ConfirmMode.AUTO` SHALL mean automatic interaction approval only after every preceding authority gate has passed; `--yes` SHALL only select that mode.

#### Scenario: Auto cannot create principal or scope
- **WHEN** interaction mode is `auto` but the principal is missing or a required scope is absent
- **THEN** the matrix denies for the principal/scope reason and does not represent the action as authorized

#### Scenario: Auto cannot authenticate
- **WHEN** interaction mode is `auto` but a required exact-action authentication proof is missing or invalid
- **THEN** the matrix denies for the authentication reason without treating automatic interaction as proof

#### Scenario: Auto cannot create or repair a grant
- **WHEN** interaction mode is `auto` but a required grant is missing, expired, revoked, invalid, or scope-insufficient
- **THEN** the matrix denies for the grant reason and no persistent grant state changes

#### Scenario: Interactive approval is not persistent authority
- **WHEN** a user approves one pending confirmation
- **THEN** that decision may allow only the current otherwise-authorized action and does not create a grant or reusable authentication evidence

### Requirement: Trust decision reasons and evidence are stable
Each matrix state SHALL map to a documented stable reason code. Product result, tracker, session, and audit evidence SHALL carry the same matrix version, normalized outcome, reason, and non-secret decision vector for one action. Existing detailed scope, authentication, policy, and grant metadata MAY remain alongside the normalized matrix evidence, but MUST NOT contradict it.

#### Scenario: Equivalent vector is deterministic
- **WHEN** the same complete decision vector is evaluated repeatedly
- **THEN** every evaluation returns the same outcome, reason code, matrix version, and normalized vector

#### Scenario: Denial evidence identifies the winning gate
- **WHEN** multiple dimensions in a vector would deny
- **THEN** evidence records the first denial under matrix precedence as the normalized reason while retaining sanitized subordinate evidence

#### Scenario: Evidence contains no authority secret
- **WHEN** matrix evidence is serialized
- **THEN** it contains only enum states, risk, interaction, version, outcome, and stable reasons, without raw principal IDs, resources, credentials, challenges, tokens, or grant IDs


### Requirement: Trust Tier runtime selects confirmation and optional grant consumption
Product security contexts SHALL carry an explicit Trust Tier of `0`, `1`, or `2` (default `0`). The dispatcher SHALL translate the tier, canonical action risk, and optional exact grant lookup into matrix grant and interaction inputs without reordering matrix version 1 deny precedence. Tier 0 SHALL require confirmation for every risk including read and SHALL NOT skip confirmation via grant. Tier 1 SHALL allow read without confirmation; SHALL allow mutate without confirmation only when an exact matching grant is valid; and SHALL still require confirmation for high-risk after authentication. Tier 2 SHALL auto-approve interaction after authority gates pass, recording a valid grant when present and `trust_grant_not_required` when absent without denying for absence. Selecting Tier 2 SHALL require principal scope `high-risk:manage` and a fresh high-risk step-up authentication before the context is used for product tools. `--yes` and `ConfirmMode` SHALL remain interaction-only and SHALL NOT select a tier or create a grant. Exact grant lookup SHALL occur only on the mandatory dispatcher path.

#### Scenario: Default Tier 0 confirms reads
- **WHEN** a product read tool runs under Tier 0 without automatic confirmation approval
- **THEN** the action requires confirmation and is not executed until interaction allows it

#### Scenario: Tier 1 mutate uses exact grant to skip confirmation
- **WHEN** Tier 1 mutate runs with an exact matching active grant for the principal, action, resource, and required scopes
- **THEN** the matrix grant state is allowed, interaction is treated as automatic approval, and the handler may run without a prompt

#### Scenario: Tier 1 mutate without grant still confirms
- **WHEN** Tier 1 mutate runs and lookup finds no matching grant
- **THEN** grant state is not required, confirmation follows `ConfirmMode`, and `--yes` only supplies automatic interaction

#### Scenario: Invalid grant remains denying under Tier 1
- **WHEN** Tier 1 mutate lookup returns revoked, expired, invalid, or scope-insufficient for the exact action
- **THEN** the matrix denies for the grant reason and confirmation or `--yes` cannot allow the action

#### Scenario: Tier cannot override earlier denial
- **WHEN** policy, scope, or authentication denies an action under any Trust Tier including Tier 2 with `--yes`
- **THEN** the matrix keeps the earlier denial reason and the handler does not run

#### Scenario: Tier 2 selection requires step-up
- **WHEN** a caller requests Trust Tier 2 without fresh high-risk authentication or without `high-risk:manage`
- **THEN** the product path refuses to install or use that Tier 2 context for tools

#### Scenario: Persisted grant is looked up only through the dispatcher
- **WHEN** a product tool action runs under a tier that may consume grants
- **THEN** exact lookup occurs on the mandatory dispatcher path and Crew adapters do not perform a parallel grant decision

### Requirement: Dispatcher evidence carries pipeline attempt correlation
While execution or escalation is active, every dispatcher-owned tool result, tracker summary, session tool record, and durable audit attempt/result SHALL carry the same non-empty pipeline attempt identifier in addition to existing request/action/session correlation. The identifier SHALL label orchestration evidence only and SHALL NOT create authority, authentication, a trust grant, a Trust Tier selection, or a second security decision.

#### Scenario: Tool evidence agrees across stores
- **WHEN** one product tool action runs during a pipeline attempt with tracker, session, and durable audit enabled
- **THEN** the returned metadata, tracker summary, session record, and both audit phases carry the same pipeline attempt identifier and existing request/action correlation

#### Scenario: Prior attempt audit remains retained
- **WHEN** a failed attempt is followed by an escalation attempt
- **THEN** durable evidence for the failed attempt remains append-only and distinguishable from evidence for the escalation attempt

#### Scenario: Attempt identifier grants no authority
- **WHEN** an action has a valid pipeline attempt identifier but fails policy, scope, authentication, grant, risk, or interaction requirements
- **THEN** the action remains denied by the existing matrix reason and the identifier does not alter the decision
