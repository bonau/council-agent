## 1. Session Module

- [ ] 1.1 Implement `SessionManager` in `sandbox/session.py` (create, append tool log, finalize)
- [ ] 1.2 Define `.council/config.yaml` schema and loader
- [ ] 1.3 Add `tests/test_sandbox_session.py`

## 2. Sandbox CLI

- [ ] 2.1 Add `council sandbox init` and `council sandbox status` subcommands
- [ ] 2.2 Add `--workspace` flag to `council run` and sandbox commands
- [ ] 2.3 Add `tests/test_cli_sandbox.py`

## 3. CrewAI Tool Integration

- [ ] 3.1 Create CrewAI `@tool` wrappers for all six tools
- [ ] 3.2 Wire wrappers through `ToolCallTracker` with `max_tool_calls`
- [ ] 3.3 Mount tools on Execution Crew agent
- [ ] 3.4 Add `tests/test_crew_tools.py`

## 4. Orchestrator Integration

- [ ] 4.1 Create session at run start when `.council/` exists
- [ ] 4.2 Populate `ExecutionResult.tool_summaries` from tracker automatically
- [ ] 4.3 Finalize session after run completes
- [ ] 4.4 Add `tests/test_sandbox_e2e.py` (tmp project, mock LLM)

## 5. Documentation

- [ ] 5.1 Update README with sandbox workflow examples
- [ ] 5.2 Update ROADMAP 現況 when implementation complete

## 6. Verification

- [ ] 6.1 Run `uv run pytest`
- [ ] 6.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [ ] 6.3 Run `npx @fission-ai/openspec@latest validate --specs --strict`
