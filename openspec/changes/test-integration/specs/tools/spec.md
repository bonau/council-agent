## ADDED Requirements

### Requirement: run_tests executes pytest with structured report

The system SHALL provide `run_tests(path: str = ".", args: str = "", *, timeout_sec: int = 120) -> ToolResult` that runs pytest within the workspace. On completion, `metadata` SHALL include `exit_code`, `passed`, `failed`, `skipped`, and `failures` (list of failure summary strings). `success` SHALL be True only when exit code is 0.

#### Scenario: All tests pass

- **WHEN** `run_tests` is executed and all tests pass
- **THEN** it returns `success=True`, `metadata.exit_code` is 0, and `metadata.failed` is 0

#### Scenario: Some tests fail

- **WHEN** `run_tests` is executed and one or more tests fail
- **THEN** it returns `success=False`, `metadata.exit_code` is non-zero, and `metadata.failures` contains at least one summary string

#### Scenario: Test path outside workspace

- **WHEN** `run_tests` is called with a path outside the workspace root
- **THEN** it returns `success=False` with a workspace boundary error

#### Scenario: Custom pytest args

- **WHEN** `run_tests` is called with additional `args` (e.g. `-k test_foo`)
- **THEN** those arguments are passed to pytest
