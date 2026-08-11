## ADDED Requirements

### Requirement: Audit directory created with sandbox init

Sandbox initialization SHALL ensure `.council/audit/` exists under the project root (idempotently). Initialization SHALL NOT delete existing audit events.

#### Scenario: Init creates audit directory

- **WHEN** `council sandbox init` (or equivalent init API) runs on a project
- **THEN** `.council/audit/` exists afterward

#### Scenario: Re-init preserves audit events

- **WHEN** sandbox init runs again on a project that already has audit events
- **THEN** existing audit event files remain intact

### Requirement: Audit log distinct from session tool logs

Session persistence under `.council/sessions/<id>/tools.jsonl` SHALL remain the per-run operational tool log. The audit log under `.council/audit/` SHALL be the cross-session security audit trail. Both MAY record the same invocation without replacing each other.

#### Scenario: Session and audit both retain records

- **WHEN** a tool runs during a sandboxed council run
- **THEN** the invocation may appear in the session `tools.jsonl` and also as an audit event under `.council/audit/`
