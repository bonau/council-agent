## 1. Session Module

- [x] 1.1 Implement `SessionManager` in `sandbox/session.py` (create, append tool log, finalize)
- [x] 1.2 Define `.council/config.yaml` schema and loader
- [x] 1.3 Add `tests/test_sandbox_session.py`

## 2. Sandbox CLI

- [x] 2.1 Add `council sandbox init` and `council sandbox status` subcommands
- [x] 2.2 Add `--workspace` flag to `council run` and sandbox commands
- [x] 2.3 Add `tests/test_cli_sandbox.py`

## 3. CrewAI Tool Integration

- [x] 3.1 Create CrewAI `@tool` wrappers for all six tools
- [x] 3.2 Wire wrappers through `ToolCallTracker` with `max_tool_calls`
- [x] 3.3 Mount tools on Execution Crew agent
- [x] 3.4 Add `tests/test_crew_tools.py`

## 4. Orchestrator Integration

- [x] 4.1 Create session at run start when `.council/` exists
- [x] 4.2 Populate `ExecutionResult.tool_summaries` from tracker automatically
- [x] 4.3 Finalize session after run completes
- [x] 4.4 Add `tests/test_sandbox_e2e.py` (tmp project, mock LLM)

## 5. Documentation

- [x] 5.1 Update README with sandbox workflow examples
- [x] 5.2 Update ROADMAP 現況 when implementation complete

## 6. Verification

- [x] 6.1 Run `uv run pytest`
- [x] 6.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [x] 6.3 Run `npx @fission-ai/openspec@latest validate --specs --strict`
