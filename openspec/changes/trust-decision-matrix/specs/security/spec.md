## ADDED Requirements

### Requirement: Versioned trust decision matrix is the authority contract
The system SHALL expose one versioned, deterministic trust-decision contract whose complete input vector contains project-policy disposition, principal/scope disposition, authentication disposition, trust-grant disposition, canonical action risk, and interaction disposition. Its output SHALL be exactly `deny`, `require_confirmation`, or `allow`, with one stable reason code and a JSON-safe representation of every non-secret input dimension. Matrix version 1 SHALL evaluate denials in this order: policy, principal/scope, authentication, grant; only after those gates pass SHALL action risk and interaction affect the result.

#### Scenario: Policy denial has highest authority precedence
- **WHEN** a decision vector contains a policy denial together with any scope, authentication, grant, risk, or interaction values
- **THEN** the result is `deny` with the corresponding stable policy reason and no later dimension can replace it

#### Scenario: Scope denial precedes authentication grant and interaction
- **WHEN** policy passes but principal/scope is missing, invalid, revoked, mismatched, or insufficient
- **THEN** the result is `deny` with the corresponding stable scope reason regardless of authentication, grant, action risk, confirmation approval, or automatic interaction

#### Scenario: Authentication denial precedes grant and interaction
- **WHEN** policy and scope pass but required authentication is missing, invalid, failed, expired, revoked, replayed, binding-mismatched, or unavailable because of a provider error
- **THEN** the result is `deny` with the corresponding stable authentication reason regardless of grant or interaction

#### Scenario: Invalid grant cannot be overridden
- **WHEN** policy, scope, and authentication pass but a required grant is missing, invalid, revoked, expired, or insufficient
- **THEN** the result is `deny` with the corresponding stable grant reason regardless of action risk or interaction mode

#### Scenario: Risk determines whether interaction is needed
- **WHEN** all authority gates pass and an action's risk requires confirmation but no confirmation outcome exists
- **THEN** the result is `require_confirmation` with reason `confirmation_required`

#### Scenario: Passed authority and resolved interaction allow
- **WHEN** all authority gates pass and the action either needs no interaction or has a permitted automatic, compatibility, or explicit approval outcome
- **THEN** the result is `allow` with reason `decision_allowed`

### Requirement: Confirmation is interaction only
Confirmation mode and confirmation outcomes SHALL control only how a decision that reached the interaction stage is resolved. They SHALL NOT create, select, restore, satisfy, or expand a principal, scope, authentication proof, trust grant, or project-policy permission. `ConfirmMode.AUTO` SHALL mean automatic interaction approval only after every preceding authority gate has passed; `--yes` SHALL only select that mode.

#### Scenario: Auto cannot create principal or scope
- **WHEN** interaction mode is `auto` but the principal is missing or a required scope is absent
- **THEN** the matrix denies for the principal/scope reason and does not represent the action as authorized

#### Scenario: Auto cannot authenticate
- **WHEN** interaction mode is `auto` but a required exact-action authentication proof is missing or invalid
- **THEN** the matrix denies for the authentication reason without treating automatic interaction as proof

#### Scenario: Auto cannot create or repair a grant
- **WHEN** interaction mode is `auto` but a required grant is missing, expired, revoked, invalid, or scope-insufficient
- **THEN** the matrix denies for the grant reason and no persistent grant state changes

#### Scenario: Interactive approval is not persistent authority
- **WHEN** a user approves one pending confirmation
- **THEN** that decision may allow only the current otherwise-authorized action and does not create a grant or reusable authentication evidence

### Requirement: Trust decision reasons and evidence are stable
Each matrix state SHALL map to a documented stable reason code. Product result, tracker, session, and audit evidence SHALL carry the same matrix version, normalized outcome, reason, and non-secret decision vector for one action. Existing detailed scope, authentication, policy, and grant metadata MAY remain alongside the normalized matrix evidence, but MUST NOT contradict it.

#### Scenario: Equivalent vector is deterministic
- **WHEN** the same complete decision vector is evaluated repeatedly
- **THEN** every evaluation returns the same outcome, reason code, matrix version, and normalized vector

#### Scenario: Denial evidence identifies the winning gate
- **WHEN** multiple dimensions in a vector would deny
- **THEN** evidence records the first denial under matrix precedence as the normalized reason while retaining sanitized subordinate evidence

#### Scenario: Evidence contains no authority secret
- **WHEN** matrix evidence is serialized
- **THEN** it contains only enum states, risk, interaction, version, outcome, and stable reasons, without raw principal IDs, resources, credentials, challenges, tokens, or grant IDs

### Requirement: v0.9.8 does not enable Trust Tier runtime
The decision contract SHALL be usable by a future Trust Tier runtime without defining or enabling Tier 0/1/2 selection in v0.9.8. Product contexts in this version SHALL represent runtime grant consumption as not required unless an explicit test or future caller supplies a complete grant disposition; persisted grants SHALL NOT be consumed automatically. No `--trust-tier` option SHALL be exposed.

#### Scenario: Stored grant remains disconnected from product tools
- **WHEN** a v0.9.8 product tool action runs while the user-owned store contains a matching grant
- **THEN** the dispatcher does not load that store or convert the record into runtime authority

#### Scenario: No tier CLI exists
- **WHEN** a user inspects `council run` options in v0.9.8
- **THEN** no `--trust-tier` option or Tier 0/1/2 runtime behavior is available
