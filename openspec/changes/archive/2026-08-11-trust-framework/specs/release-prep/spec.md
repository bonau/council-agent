## MODIFIED Requirements

### Requirement: Alpha and beta admission gates
v1.0-alpha Trust Tier runtime work MAY proceed only after all P0 and P1 items assigned to v0.9.1–v0.9.9 are closed with verification evidence, those patch changes are archived, `./scripts/check.sh` passes, and admission evidence for smoke plus Agent checklist is recorded under `docs/releases/evidence/`. When an independent human manual cannot run in the execution environment, maintainers MAY record an explicit accepted-gate rationale approved for that run instead of fabricating a human PASS. Public beta SHALL NOT open while any P0 remains open, and SHALL require the Trust Tier alpha change to be archived with frozen tier/principal/grant/authentication/audit contracts plus a fixed beta tag/commit announcement.

#### Scenario: Alpha blocked by open P0
- **WHEN** a P0 item such as unique middleware bypass or shell containment failure remains open
- **THEN** Agents MUST NOT claim v1.0-alpha admission is satisfied and MUST NOT start Trust Tier runtime implementation under this preparation contract

#### Scenario: Alpha admitted with recorded evidence
- **WHEN** P0/P1 are closed, check.sh passes, smoke SMK-00–09 pass, and Agent checklist evidence is stored for the candidate baseline
- **THEN** Agents MAY start the Trust Tier runtime OpenSpec change and MUST link the evidence directory from the learning log

#### Scenario: Beta blocked by open P0
- **WHEN** maintainers consider announcing public beta
- **THEN** announcement is allowed only if the known-issues list shows every P0 closed with regression evidence and the announced beta ref is recorded

### Requirement: v0.9.x handoff stops before Trust Tier runtime
After the v0.9.9 debt sequence and alpha admission evidence are recorded, the handoff SHALL state that v0.9.1–v0.9.9 is complete and that the next feature sequence is the Trust Tier runtime change (`trust-framework`) through alpha and beta tags. The handoff SHALL NOT claim Trust Tier was implemented inside the v0.9.x debt patches, and SHALL NOT treat feature-branch completion as a package bump. Package version files for debt patches remain release-branch work; alpha/beta version bumps occur only on their release branches.

#### Scenario: Final debt handoff is explicit
- **WHEN** a maintainer reads the v0.9.x handoff after the evidence-closure change is archived
- **THEN** it says the v0.9.1–v0.9.9 debt sequence is complete and stops before implementing Trust Tier inside those patches, recording the v0.9.9 evidence and archive paths

#### Scenario: Version remains release-branch work
- **WHEN** the v0.9.9 feature branch completes
- **THEN** project package version files remain unchanged and the handoff identifies any version bump or tag as separate release-branch work

#### Scenario: Post-admission handoff points to trust-framework
- **WHEN** a maintainer reads the handoff after alpha admission evidence lands
- **THEN** it identifies `trust-framework` / Trust Tier runtime as the next action and links admission evidence paths
