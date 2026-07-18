## Why

v0.5 的 `run_command` 以 `shell=True` 執行任意指令，僅有 workspace cwd 邊界，無指令內容防護。v0.6 需加入指令分類器，在執行前依 pattern 將指令分為 `read` / `write` / `dangerous`，對危險指令預設拒絕，堵住最明顯的破壞性操作空窗。

## What Changes

- 新增 `src/council_agent/security/` 模組與 `classifier.py`：以 regex/pattern 比對指令字串並回傳分類結果
- `run_command` 執行前經分類器檢查；`dangerous` 預設拒絕並回傳 `ToolResult(success=False)`（不 raise）
- 分類結果寫入 `metadata`（如 `classification`），供後續 Verification／審計使用
- 新增單元測試（分類 pattern）與整合測試（危險指令被拒絕、安全指令仍可執行）
- 更新 README 安全提示：v0.6 起有基本指令分類，但仍非完整信任框架
- **不**改變 filesystem tools 行為（寫入仍由 WorkspaceGuard 保護）
- **不**對 `run_tests` 另行分類（其內部呼叫 `run_command`，會一併受檢）

## Non-goals

對齊 ROADMAP v0.6（其餘屬後續里程碑）：

- 互動式確認／`--yes`／無 TTY 行為（v0.7）
- 審計日誌與 `council audit`（v0.8）
- `council.policy.yaml` 自訂允許／拒絕 pattern（v0.9）
- Trust Tier、`council trust`、Policy Middleware 完整鏈（v1.0）
- 完整 shell AST 解析或跨平台 shell 語義模擬
- 宣稱已具備完整安全機制（分類為 pattern 啟發式，可被繞過）

## Capabilities

### New Capabilities

- `security`: 指令分類（`read` / `write` / `dangerous`）、危險指令預設拒絕、可擴充之 pattern 表

### Modified Capabilities

- `tools`: `run_command` SHALL 在執行前經指令分類器檢查；危險指令 SHALL 拒絕且不啟動 subprocess

## Impact

- **新增**：`src/council_agent/security/`（`__init__.py`、`classifier.py`）
- **修改**：`src/council_agent/tools/shell.py`（入口插入分類檢查）
- **新增**：`tests/test_command_classifier.py`、`tests/test_run_command_classification.py`
- **修改**：`README.md`（安全提示）、必要時 `AGENTS.md` 模組地圖（允許 `security/`）
- **不變**：CLI 簽名、Orchestrator 流程、filesystem tools、CrewAI wrapper 簽名
- **無新依賴**：僅使用 Python 標準庫（`re`、`enum`／`dataclasses`）
