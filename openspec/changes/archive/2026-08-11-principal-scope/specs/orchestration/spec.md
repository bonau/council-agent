## MODIFIED Requirements

### Requirement: Orchestrator owns one security context lifecycle

Before a product pipeline can invoke tools, the orchestrator SHALL require a Council principal separately from the OpenRouter provider credential and SHALL construct and install one validated security context containing the resolved workspace, loaded project-policy snapshot, resolved confirmation policy, per-run tracker, request/session correlation, expected principal identity/current-authority source, optional sandbox session writer, and optional sandbox audit logger. The same context SHALL remain active through execution and escalation, current principal authority SHALL be resolved for each action, and the context SHALL be cleaned up on every success or failure path.

#### Scenario: One context spans execution and escalation

- **WHEN** a run reaches execution and subsequently escalation
- **THEN** all product tool invocations in both phases observe the same request, workspace, policy snapshot, confirmation policy, tracker, session, audit correlation, and expected principal identity

#### Scenario: Run failure cleans context

- **WHEN** planning, execution, verification, or escalation raises an exception
- **THEN** the orchestrator closes and resets the installed security context before returning or re-raising

#### Scenario: Later run cannot inherit prior context

- **WHEN** one run completes and another caller invokes a public tool outside a newly installed run context
- **THEN** the tool fails closed rather than inheriting principal, policy, confirmation, tracker, session, or audit state from the completed run

#### Scenario: Missing principal fails before crews

- **WHEN** a library run omits its Council principal
- **THEN** the run fails closed before constructing crews and does not treat the provider credential or session identifier as a principal

## ADDED Requirements

### Requirement: Provider credential and Council principal use separate data flows

The CLI and orchestration API SHALL load and pass the OpenRouter API key as a typed provider credential used only to construct model clients. They SHALL independently resolve and pass a Council principal used only for tool authorization. Supplying one SHALL NOT synthesize, validate, or expand the other, and diagnostic output SHALL NOT echo raw credential or principal identifier values.

#### Scenario: Model builders receive provider credential only

- **WHEN** the orchestrator constructs planning, execution, verification, or escalation model clients
- **THEN** each builder receives the typed OpenRouter provider credential and no Council scope data

#### Scenario: Security context receives principal only

- **WHEN** the orchestrator constructs the run security context
- **THEN** it receives the Council principal/current-authority source and no OpenRouter API key

#### Scenario: Provider credential is not accepted as principal

- **WHEN** a caller passes a provider credential in the Council-principal position
- **THEN** orchestration fails before the pipeline and no tool authority is installed

### Requirement: CLI principal configuration is strict and independent

The CLI SHALL resolve a stable local Council principal identifier, recognized kind/issuer, and explicit scope set independently of `OPENROUTER_API_KEY`. It SHALL provide a full recognized local scope set by default for compatibility, SHALL allow the scope set to be narrowed through Council-specific configuration, and SHALL fail before the pipeline on unknown scope names. This local declaration SHALL NOT be represented as session authentication or a persistent trust grant.

#### Scenario: Default local CLI principal preserves supported tool access

- **WHEN** no Council-specific scope override is configured
- **THEN** the CLI constructs a stable local principal with the full recognized scope set while keeping the OpenRouter key separate

#### Scenario: Read-only CLI principal is narrowed

- **WHEN** Council-specific scope configuration contains only `read`
- **THEN** the resulting principal can proceed to read-tool gates and is denied for mutation, test, and shell actions

#### Scenario: Unknown configured scope fails fast

- **WHEN** Council-specific scope configuration includes an unrecognized value
- **THEN** the CLI reports a sanitized configuration error and does not start the pipeline
