## ADDED Requirements

### Requirement: Product tools honor Trust Tier through the dispatcher only
All public filesystem and shell product tools SHALL obtain Trust Tier, grant disposition, and confirmation outcomes exclusively from the mandatory security dispatcher. Direct library callers and Crew adapters SHALL NOT implement a second tier or grant decision. Under Tier 0, read tools SHALL be subject to the confirmation gate. Under Tier 1 or Tier 2, grant-assisted or automatic interaction SHALL still be blocked by policy, scope, authentication, or denying grant states with no file or process side effects.

#### Scenario: Direct and Crew paths share tier evidence
- **WHEN** the same tool action runs under equivalent SecurityContext tiers via direct library and Crew adapter entry points
- **THEN** both return the same matrix outcome, reason, trust tier label, and grant disposition without duplicate authority writers

#### Scenario: Denied tier action has no side effects
- **WHEN** a tier-driven confirmation refusal or grant denial occurs for write or shell tools
- **THEN** the target file or outside sentinel is unchanged and no subprocess starts
