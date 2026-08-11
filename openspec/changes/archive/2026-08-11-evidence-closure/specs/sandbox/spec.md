## ADDED Requirements

### Requirement: Session tool evidence preserves pipeline attempts
For a sandboxed pipeline run, each persisted session tool-call line created during execution or escalation SHALL include the pipeline attempt identifier supplied by orchestration. Session persistence SHALL append later-attempt records without rewriting or deleting records from earlier attempts.

#### Scenario: Failed and final attempts remain distinguishable
- **WHEN** an initial attempt records tool actions, fails Verification, and an escalation records additional actions
- **THEN** `tools.jsonl` retains both ordered sets with different pipeline attempt identifiers and their original request/action/audit correlation

#### Scenario: Session attempt correlation matches final result
- **WHEN** a caller follows the final result's attempt identifier to session tool evidence
- **THEN** every selected session line belongs to that final attempt and preserves its existing audit attempt/result event references
