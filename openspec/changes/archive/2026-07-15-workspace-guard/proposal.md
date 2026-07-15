## Why

Council Agent v0.2 的 tool 函式可存取任意路徑，無 workspace 邊界保護。v0.3 需加入 `WorkspaceGuard`，限制所有檔案與 shell 操作在當前工作目錄內，阻擋路徑穿越、symlink 逃逸與敏感檔案存取，為後續 Sandbox MVP（v0.5）與安全補強（v0.6+）奠定基礎。

## What Changes

- 新增 `src/council_agent/sandbox/workspace.py`：`WorkspaceGuard` 路徑驗證與敏感路徑黑名單
- 新增 `COUNCIL_WORKSPACE_ROOT` 環境變數（預設 cwd）
- 在 `read_file`、`write_file`、`list_dir`、`delete_file`、`run_command` 開頭插入 guard（函式簽名不變）
- 新增路徑驗證單元測試（含 symlink、穿越攻擊案例）
- 更新 `.env.example` 說明
- **不**修改 CLI、Orchestrator、Execution Crew（留待 v0.5）
- **不**實作 `council sandbox` 子命令（留待 v0.5）

## Capabilities

### New Capabilities

- `sandbox`: WorkspaceGuard 路徑邊界驗證、敏感路徑黑名單、`COUNCIL_WORKSPACE_ROOT` 設定

### Modified Capabilities

- `tools`: 移除「無 workspace 邊界」要求，改為所有 path/cwd 操作 SHALL 經 WorkspaceGuard 驗證

## Impact

- **新增**：`src/council_agent/sandbox/`（`workspace.py`、`__init__.py`）
- **修改**：`src/council_agent/tools/filesystem.py`、`shell.py`
- **修改**：`src/council_agent/config/settings.py`、`.env.example`
- **新增**：`tests/test_workspace_guard.py`、`tests/test_tools_workspace_integration.py`、`tests/conftest.py`
- **修改**：既有 tool 測試需設定 workspace root fixture
- **無新依賴**：僅使用 Python 標準庫（`pathlib`、`fnmatch`）
