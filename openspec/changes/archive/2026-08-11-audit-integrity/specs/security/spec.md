## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Argument truncation in audit records
String values that exceed a fixed size limit SHALL be truncated in stored audit and session evidence with an explicit truncation marker. Recursive secret redaction SHALL occur before truncation so truncation cannot leave a secret prefix on disk. Sanitization and truncation SHALL NOT change actual tool execution arguments or returned tool results.

#### Scenario: Large string arg truncated in audit only
- **WHEN** a tool is invoked with a non-secret string argument larger than the audit size limit
- **THEN** the audit record stores a truncated value with a truncation marker while the tool still receives the full argument

#### Scenario: Large secret is redacted before truncation
- **WHEN** a value contains a recognized secret longer than the storage limit
- **THEN** persisted evidence contains the redaction marker and no retained prefix of the secret
