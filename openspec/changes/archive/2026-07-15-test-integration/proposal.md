## Why

Council Agent v0.3 已具備 workspace 邊界的 tool 基礎層，但 Verification 仍僅靠 LLM 自評 execution 文字輸出，無法對照真實測試結果。v0.4 需加入 `run_tests` tool、結構化測試報告，並讓 Verification 參考 tool 執行摘要與 exit code，同時以 `max_tool_calls` 防止 tool 呼叫迴圈失控。

## What Changes

- 新增 `run_tests(path, args)` tool，封裝 pytest 並回傳 passed / failed / skipped 計數與失敗摘要
- 新增 `ToolCallSummary` 與 tool 呼叫追蹤機制，Orchestrator 收集並傳遞至 Verification
- 升級 Verification crew prompt：要求對照測試 exit code、計數與 plan 成功標準
- 新增 `max_tool_calls` 設定（Settings + Preset），超過上限時停止 tool 執行
- 新增整合測試：mock LLM + 真實 tool 在暫存目錄執行
- **不**掛載 tools 至 Execution Crew（留待 v0.5）
- **不**實作 `council sandbox` CLI（留待 v0.5）

## Capabilities

### New Capabilities

- `orchestration`: Tool 呼叫追蹤、`max_tool_calls` 限制、Verification 接收 tool 執行摘要

### Modified Capabilities

- `tools`: 新增 `run_tests` 需求；`run_command` 維持不變

## Impact

- **修改**：`src/council_agent/tools/shell.py`（新增 `run_tests`）
- **修改**：`src/council_agent/tools/__init__.py`
- **新增**：`src/council_agent/tools/tracker.py`（tool 呼叫追蹤與上限）
- **修改**：`src/council_agent/types.py`（`ToolCallSummary`、`ExecutionResult.tool_summaries`）
- **修改**：`src/council_agent/config/settings.py`、`presets.py`（`max_tool_calls`）
- **修改**：`src/council_agent/orchestrator.py`、`crews/verification.py`
- **新增**：`tests/test_tools_run_tests.py`、`tests/test_tool_tracker.py`、`tests/test_verification_integration.py`
- **無新依賴**：pytest 為 dev/test 既有依賴
