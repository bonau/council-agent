## ADDED Requirements

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
