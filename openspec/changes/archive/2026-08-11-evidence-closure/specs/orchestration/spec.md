## ADDED Requirements

### Requirement: Verification and escalation close evidence per attempt
The pipeline SHALL assign a non-empty unique attempt identifier to the initial execution and to every escalation execution. Each attempt SHALL retain its own execution output, tool summaries, verification verdict, and sequence position. After every escalation, the pipeline SHALL run Verification again against the original plan and success criteria. The final output, verdict, tool summaries, decision correlation, and final attempt identifier SHALL all select the same last attempt; evidence from prior attempts SHALL remain available.

#### Scenario: Escalation passes re-verification
- **WHEN** initial Verification fails, an allowed escalation produces a new execution, and Verification of that new execution passes
- **THEN** the final verdict is PASS and the final output, summaries, and final attempt identifier all refer to the passing escalation attempt while the failed initial attempt remains retained

#### Scenario: Escalation still fails
- **WHEN** Verification continues to fail after the configured escalation limit is exhausted
- **THEN** the pipeline returns the last FAIL verdict, the last failed output, a retries-exhausted stop reason, and the complete ordered attempt history

#### Scenario: Initial execution passes
- **WHEN** the initial execution passes Verification
- **THEN** no escalation runs and the initial attempt is also the final attempt

### Requirement: Escalation uses the execution tool boundary
Escalation SHALL receive the same dispatcher-backed product tool adapters and the same run-scoped security context as initial execution. Tool summaries SHALL be partitioned by pipeline attempt even though the per-run tool-call limit remains cumulative.

#### Scenario: Escalation invokes a tool
- **WHEN** an escalation uses a product tool to correct a failed execution
- **THEN** the action passes through the existing mandatory dispatcher and appears only in that escalation attempt's summaries with its attempt correlation

#### Scenario: Tool limit spans retries
- **WHEN** initial execution and escalation both invoke tools
- **THEN** all calls consume the one run-level tool-call budget while each attempt exposes only the summaries created during that attempt

### Requirement: Verification fails closed on required evidence
Verification SHALL apply deterministic evidence checks in addition to the verifier model's response. When the request, plan, or success criteria require a product tool or test result, PASS SHALL require matching evidence from the current attempt. Required pytest evidence SHALL include a successful `run_tests` result with exit code zero and zero failed tests. Current-attempt tool evidence SHALL carry matching attempt, request, action, and normalized decision correlation. A model-generated PASS SHALL be converted to FAIL when required evidence is missing, malformed, failed, or belongs to another attempt.

#### Scenario: Missing required test evidence cannot pass
- **WHEN** success criteria require pytest or tests to pass but the current attempt has no complete successful `run_tests` summary
- **THEN** Verification returns FAIL even if the verifier model responded PASS

#### Scenario: Cross-attempt evidence cannot pass
- **WHEN** a final attempt's only relevant tool or test summary belongs to an earlier attempt identifier
- **THEN** Verification returns FAIL and identifies the attempt-correlation mismatch

#### Scenario: Text-only result needs no invented tool evidence
- **WHEN** a request and plan require only a textual deliverable and do not require a product tool, file operation, command, or test result
- **THEN** Verification may evaluate the deliverable without inventing a tool-evidence requirement
