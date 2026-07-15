## Why

Council Agent v0.1.0 的 Execution Crew 僅產出文字，無法對工作區進行檔案操作或執行 shell 指令。v0.2 需建立可重用的 tool 基礎層，作為後續 WorkspaceGuard（v0.3）、測試整合（v0.4）與 Sandbox MVP（v0.5）的共用實作基礎。

## What Changes

- 新增 `src/council_agent/tools/` 模組，包含統一 `ToolResult` 回傳結構
- 實作五個 tool 函式：`read_file`、`write_file`、`list_dir`、`delete_file`、`run_command`
- 各 tool 附單元測試（使用 pytest `tmp_path` 暫存目錄）
- **不**掛載至 Execution Crew（留待 v0.5）
- **不**實作 WorkspaceGuard 或路徑邊界（留待 v0.3）
- **不**修改 CLI、Orchestrator 或現有 crew 行為

## Capabilities

### New Capabilities

- `tools`: 可重用的檔案系統與 shell tool 函式，回傳統一 `ToolResult` 結構

### Modified Capabilities

（無 — 現有 `openspec/specs/` 尚無規格）

## Impact

- **新增**：`src/council_agent/tools/`（`base.py`、`filesystem.py`、`shell.py`、`__init__.py`）
- **新增**：`tests/test_tools_filesystem.py`、`tests/test_tools_shell.py`
- **不變**：CLI、Orchestrator、crews、現有測試行為
- **無新依賴**：僅使用 Python 標準庫（`pathlib`、`subprocess`）
