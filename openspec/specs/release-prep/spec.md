## Purpose

Defines the pre-v1.0 release preparation contract: contradiction inventory, one-major-issue-per-patch sequencing for v0.9.x, learning-log requirements, smoke and public-test documentation readiness, and alpha/beta admission gates. This capability governs process and documentation readiness before Trust Tier runtime work begins.

## Requirements

### Requirement: Contradiction inventory before major-version feature work
The project SHALL maintain a contradiction inventory comparing ROADMAP commitments, main OpenSpec specs, archived change Non-goals, implementation behavior, tests, and user-facing docs before starting Trust Tier or other v1.0 feature work. Each contradiction SHALL be graded P0, P1, or P2 with a responsible patch or prerelease version.

#### Scenario: Inventory exists before Trust Tier change
- **WHEN** an Agent prepares to open a Trust Tier or Policy Middleware runtime change for v1.0-alpha
- **THEN** `docs/releases/v1.0-alpha-known-issues.md` (or successor) lists open P0/P1 items with responsible versions, and no Trust Tier runtime change is started while any P0 remains open without a closing evidence path

#### Scenario: Optimistic source is not preferred
- **WHEN** ROADMAP, main specs, archive notes, and code disagree about a security guarantee
- **THEN** the inventory records a conflict item and treats the disagreement as unresolved until specs, code, tests, and docs are realigned

### Requirement: One major issue per v0.9.x patch
v0.9.x patch planning SHALL assign exactly one major security or evidence invariant per patch version. A patch MAY include tests, specs, and documentation required to close that invariant, but SHALL NOT implement the next patch's major capability in the same release.

#### Scenario: Fixed sequence is published
- **WHEN** readers consult ROADMAP or the v1 preparation learning log for pre-alpha patches
- **THEN** they find the ordered sequence v0.9.1 shell containment, v0.9.2 unique middleware/dispatcher, v0.9.3 policy trust boundary and versioned schema, v0.9.4 audit integrity substrate, v0.9.5 principal/API key scope, v0.9.6 session authentication foundation, v0.9.7 user-owned trust grant store, v0.9.8 Trust Tier decision matrix separated from ConfirmMode, and v0.9.9 verification/escalation evidence closure plus documentation correction

#### Scenario: Trust Tier runtime remains out of patch scope
- **WHEN** a v0.9.x OpenSpec change is proposed under this preparation contract
- **THEN** its Non-goals explicitly exclude enabling Trust Tier 0/1/2 runtime behavior, `council trust` grant semantics as product authorization, and claiming a complete trust framework

### Requirement: Learning log at each preparation step
Each preparation, patch planning, verification, archive, release-gate, or admission decision step SHALL append a dated learning-log entry under `docs/releases/` that records status, baseline commit/version, observations, risks, decisions, verification evidence paths, remaining risks, documentation impact, and the single next action.

#### Scenario: Step completes with log entry
- **WHEN** an Agent finishes a preparation step such as inventory, smoke design, or document landing
- **THEN** `docs/releases/learning-log-v1-prep.md` (or the active major-prep learning log) gains a new dated entry that does not overwrite prior conclusions

#### Scenario: Secrets are not logged
- **WHEN** evidence contains API keys, tokens, passphrases, or other secrets
- **THEN** the learning log and public evidence store only redacted summaries or hashes, never raw secrets

### Requirement: Smoke and public-test documentation readiness
Before inviting public beta testers, the project SHALL publish human and Agent testing materials covering isolation requirements, known limitations, fixed case IDs, expected outcomes, evidence collection with redaction, stop conditions, cleanup, and an issue report template. The materials SHALL distinguish the current candidate boundary from historical v0.9.0 behavior: supported product tool paths use fail-closed command analysis, a mandatory dispatcher, restrict-only project policy, scoped principals, high-risk authentication, a user-owned grant store foundation, a versioned trust-decision matrix, redacted sequenced per-event audit integrity, and attempt-scoped Verification evidence. They SHALL also state that these controls are not OS containment, an externally anchored hash chain, or Trust Tier runtime.

#### Scenario: Public testing docs are discoverable
- **WHEN** a human or Agent tester opens `docs/index.md`
- **THEN** they can reach the public testing handbook, manual cases, Agent checklist, smoke suite design, known-issues list, and issue template

#### Scenario: Shell and confirmation limitations are explicit
- **WHEN** testers read the public testing handbook or known-issues list
- **THEN** the docs distinguish current fail-closed and evidence behavior from historical v0.9.0 expected failures and explicitly retain the OS-sandbox, hostile project-code, external audit anchoring, and pre-Trust-Tier limitations

### Requirement: Alpha and beta admission gates
v1.0-alpha Trust Tier runtime work SHALL NOT start until all P0 and P1 items assigned to v0.9.1–v0.9.9 are closed with verification evidence, OpenSpec active changes for those patches are archived, and `./scripts/check.sh` passes on the candidate baseline. Public beta SHALL NOT open while any P0 remains open.

#### Scenario: Alpha blocked by open P0
- **WHEN** a P0 item such as unique middleware bypass or shell containment failure remains open
- **THEN** Agents MUST NOT claim v1.0-alpha admission is satisfied and MUST NOT start Trust Tier runtime implementation under this preparation contract

#### Scenario: Beta blocked by open P0
- **WHEN** maintainers consider announcing public beta
- **THEN** announcement is allowed only if the known-issues list shows every P0 closed with regression evidence and the announced beta ref is recorded

### Requirement: Major-release preparation playbook is executable
The repository SHALL include an Agent-executable major-release preparation playbook that covers git-flow checks, OpenSpec validation rules, contradiction inventory steps, patch sequencing, smoke gates, documentation readiness, and alpha/beta/GA admission without implementing Trust Tier itself.

#### Scenario: Playbook boundary is explicit
- **WHEN** an Agent follows `docs/releases/major-release-prep-playbook.md`
- **THEN** the playbook states that Trust Tier runtime belongs to v1.0-alpha and that bare `openspec validate --strict` without `--changes` or `--specs` MUST NOT be treated as success

### Requirement: v0.9.x handoff stops before Trust Tier runtime
After the v0.9.9 implementation, specs, evidence, and documentation gate complete, the handoff SHALL state that the v0.9.1–v0.9.9 debt sequence is complete and that this sequence stops before v1.0-alpha. The only next feature action SHALL be a separately proposed v1.0-alpha Trust Tier change. Feature-branch completion SHALL NOT be represented as a package version bump, release tag, or Trust Tier implementation.

#### Scenario: Final debt handoff is explicit
- **WHEN** a maintainer reads the v0.9.x handoff after the evidence-closure change is archived
- **THEN** it says “v0.9.1–v0.9.9 完成；下一動作是另開 v1.0-alpha Trust Tier change（本序列停止）” and records the v0.9.9 evidence and archive paths

#### Scenario: Version remains release-branch work
- **WHEN** the v0.9.9 feature branch completes
- **THEN** project package version files remain unchanged and the handoff identifies any version bump or tag as separate release-branch work
