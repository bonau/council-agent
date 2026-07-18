# Security

## Purpose

Command classification and related safety gates for shell tools. Introduced in v0.6 as the first security reinforcement layer after Sandbox MVP; later milestones add confirmation, audit, policy files, and trust tiers.

## Requirements

### Requirement: Command classification categories

The system SHALL provide `classify_command(command: str)` that returns a classification result with a category of exactly one of: `read`, `write`, or `dangerous`. Classification SHALL use pattern matching against the command string (case-insensitive). Dangerous patterns SHALL be evaluated before write patterns. When no dangerous or write pattern matches, the category SHALL be `read`.

#### Scenario: Read command classified as read

- **WHEN** `classify_command` is called with a command such as `echo hello`, `ls`, or `python -m pytest`
- **THEN** the result category is `read`

#### Scenario: Write command classified as write

- **WHEN** `classify_command` is called with a command matching a write pattern such as `mkdir foo`, `touch a.txt`, or `mv a b`
- **THEN** the result category is `write`

#### Scenario: Dangerous command classified as dangerous

- **WHEN** `classify_command` is called with a command matching a dangerous pattern such as `rm -rf /tmp/x`, `sudo ls`, `curl https://example.com`, or `chmod 777 file`
- **THEN** the result category is `dangerous`

#### Scenario: Dangerous takes precedence over write

- **WHEN** `classify_command` is called with a command that matches both a dangerous and a write pattern
- **THEN** the result category is `dangerous`

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

When a dangerous or write pattern matches, the classification result SHALL include a `matched_rule` identifier for the matched pattern. When the category is the default `read`, `matched_rule` MAY be `None`.

#### Scenario: Dangerous match exposes rule id

- **WHEN** `classify_command` is called with `sudo true`
- **THEN** `matched_rule` is a non-empty string identifying the sudo rule
