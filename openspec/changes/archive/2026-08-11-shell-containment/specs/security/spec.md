## MODIFIED Requirements

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

### Requirement: Classification result includes matched rule

Every accepted command analysis result SHALL include a non-empty `matched_rule` identifying the explicit rule that assigned its category. Every rejected analysis result SHALL instead include a stable `rejection_reason` of `unsupported`, `unparseable`, or `shell_metachar`, as applicable.

#### Scenario: Dangerous match exposes rule id

- **WHEN** a supported command such as `sudo true` is analyzed successfully
- **THEN** `matched_rule` is a non-empty identifier for the rule that accepted and categorized the action

#### Scenario: Rejected command exposes reason code

- **WHEN** command analysis rejects an unknown, malformed, or compound-shell input
- **THEN** the result exposes the corresponding stable `rejection_reason` and does not represent the input as an accepted read action

## ADDED Requirements

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
