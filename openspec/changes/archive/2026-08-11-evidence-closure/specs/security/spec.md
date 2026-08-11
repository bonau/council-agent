## ADDED Requirements

### Requirement: Dispatcher evidence carries pipeline attempt correlation
While execution or escalation is active, every dispatcher-owned tool result, tracker summary, session tool record, and durable audit attempt/result SHALL carry the same non-empty pipeline attempt identifier in addition to existing request/action/session correlation. The identifier SHALL label orchestration evidence only and SHALL NOT create authority, authentication, a trust grant, a Trust Tier selection, or a second security decision.

#### Scenario: Tool evidence agrees across stores
- **WHEN** one product tool action runs during a pipeline attempt with tracker, session, and durable audit enabled
- **THEN** the returned metadata, tracker summary, session record, and both audit phases carry the same pipeline attempt identifier and existing request/action correlation

#### Scenario: Prior attempt audit remains retained
- **WHEN** a failed attempt is followed by an escalation attempt
- **THEN** durable evidence for the failed attempt remains append-only and distinguishable from evidence for the escalation attempt

#### Scenario: Attempt identifier grants no authority
- **WHEN** an action has a valid pipeline attempt identifier but fails policy, scope, authentication, grant, risk, or interaction requirements
- **THEN** the action remains denied by the existing matrix reason and the identifier does not alter the decision
