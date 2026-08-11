## MODIFIED Requirements

### Requirement: Smoke and public-test documentation readiness
Before inviting public beta testers, the project SHALL publish human and Agent testing materials covering isolation requirements, known limitations, fixed case IDs, expected outcomes, evidence collection with redaction, stop conditions, cleanup, and an issue report template. The materials SHALL distinguish the current candidate boundary from historical v0.9.0 behavior: supported product tool paths use fail-closed command analysis, a mandatory dispatcher, restrict-only project policy, scoped principals, high-risk authentication, a user-owned grant store foundation, a versioned trust-decision matrix, redacted sequenced per-event audit integrity, and attempt-scoped Verification evidence. They SHALL also state that these controls are not OS containment, an externally anchored hash chain, or Trust Tier runtime.

#### Scenario: Public testing docs are discoverable
- **WHEN** a human or Agent tester opens `docs/index.md`
- **THEN** they can reach the public testing handbook, manual cases, Agent checklist, smoke suite design, known-issues list, and issue template

#### Scenario: Current boundaries are explicit
- **WHEN** testers read the public testing handbook, smoke suite, manual cases, or known-issues list
- **THEN** the docs distinguish current fail-closed and evidence behavior from historical v0.9.0 expected failures and explicitly retain the OS-sandbox, hostile project-code, external audit anchoring, and pre-Trust-Tier limitations

## ADDED Requirements

### Requirement: v0.9.x handoff stops before Trust Tier runtime
After the v0.9.9 implementation, specs, evidence, and documentation gate complete, the handoff SHALL state that the v0.9.1–v0.9.9 debt sequence is complete and that this sequence stops before v1.0-alpha. The only next feature action SHALL be a separately proposed v1.0-alpha Trust Tier change. Feature-branch completion SHALL NOT be represented as a package version bump, release tag, or Trust Tier implementation.

#### Scenario: Final debt handoff is explicit
- **WHEN** a maintainer reads the v0.9.x handoff after the evidence-closure change is archived
- **THEN** it says “v0.9.1–v0.9.9 完成；下一動作是另開 v1.0-alpha Trust Tier change（本序列停止）” and records the v0.9.9 evidence and archive paths

#### Scenario: Version remains release-branch work
- **WHEN** the v0.9.9 feature branch completes
- **THEN** project package version files remain unchanged and the handoff identifies any version bump or tag as separate release-branch work
