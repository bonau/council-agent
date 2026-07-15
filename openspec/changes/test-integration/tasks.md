## 1. run_tests Tool

- [x] 1.1 Implement `run_tests(path, args, timeout_sec)` in `tools/shell.py`
- [x] 1.2 Add pytest output parser for passed/failed/skipped counts and failure summaries
- [x] 1.3 Export `run_tests` from `tools/__init__.py`
- [x] 1.4 Add `tests/test_tools_run_tests.py` with pass/fail/skip cases in tmp workspace

## 2. Tool Call Tracking

- [x] 2.1 Add `ToolCallSummary` to `types.py` and extend `ExecutionResult` with `tool_summaries`
- [x] 2.2 Implement `ToolCallTracker` in `tools/tracker.py`
- [x] 2.3 Add `max_tool_calls` to Settings (`COUNCIL_MAX_TOOL_CALLS`) and optional Preset field
- [x] 2.4 Add `tests/test_tool_tracker.py`

## 3. Verification Upgrade

- [x] 3.1 Update verification prompt to include `{tool_summaries}` and test-result guidance
- [x] 3.2 Update `run_verification()` to accept and format tool summaries
- [x] 3.3 Update orchestrator to pass `execution.tool_summaries` to verification

## 4. Integration Tests

- [x] 4.1 Add `tests/test_verification_integration.py`: real tools in tmp dir + mock verification crew
- [x] 4.2 Verify orchestrator passes summaries through the pipeline

## 5. Verification

- [x] 5.1 Run `uv run pytest`
- [x] 5.2 Run `npx @fission-ai/openspec@latest validate --strict`
