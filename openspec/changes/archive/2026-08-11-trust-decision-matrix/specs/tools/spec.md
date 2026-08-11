## ADDED Requirements

### Requirement: Product tool entries share one trust decision vector
Every dispatcher-backed product tool action SHALL produce its normalized trust-decision outcome through the same versioned matrix contract. A direct library function and its Crew adapter SHALL NOT build, reorder, or override policy, scope, authentication, grant, risk, or interaction dimensions independently. A Crew adapter MAY format the returned result for an agent but SHALL preserve the dispatcher-owned result and durable audit reason.

#### Scenario: Direct and Crew denials are equivalent
- **WHEN** the same canonical action is invoked through a direct public tool and a Crew adapter under equivalent security contexts
- **THEN** both actions produce the same matrix version, normalized vector states, outcome, and stable winning reason in dispatcher-owned evidence

#### Scenario: Automatic confirmation cannot bypass a tool gate
- **WHEN** a direct or Crew tool action uses automatic confirmation but policy, scope, authentication, or a required grant denies
- **THEN** neither entry executes the private handler or produces a filesystem, subprocess, process, or network side effect

#### Scenario: Handler result does not rewrite authority
- **WHEN** an otherwise authorized operation succeeds or encounters an ordinary operational error
- **THEN** the handler cannot add a principal, scope, authentication proof, grant, or different matrix reason to elevate the decision
