## Why

v0.6 對 `dangerous` shell 指令一律硬拒絕，合法但敏感的操作（例如受控下載、清理建置產物）無法在互動環境中放行；寫入面（`write` 類 shell、`write_file`／`delete_file`）也尚無確認閘道。v0.7 需補上互動式確認與 CI 友善的 `--yes`，並在無 TTY 時安全拒絕需確認的操作。

## What Changes

- 新增 `src/council_agent/security/confirm.py`：確認模式（`ask`／`auto`／`refuse`／`compat`）、ContextVar 政策與 Rich `[Y/n]` 確認
- `run_command`：分類為 `dangerous` 或 `write` 時，依確認政策決定允許／拒絕（拒絕則不啟動 subprocess）
- `write_file`／`delete_file`：副作用前經確認閘道
- `council run --yes`：跳過所有確認；無 TTY 且未 `--yes` 時拒絕需確認操作
- Orchestrator 在 pipeline 期間安裝確認政策，結束後還原
- 函式庫／測試預設 `compat`：維持 v0.6 行為（`dangerous` 硬拒、write／filesystem 不擋），避免破壞既有單測
- 更新 README 安全提示與 `--yes` 說明
- 新增單元／整合測試涵蓋 ask／auto／refuse／compat 與無副作用拒絕

## Non-goals

對齊 ROADMAP v0.7（其餘屬後續里程碑）：

- 審計日誌與 `council audit`（v0.8）
- `council.policy.yaml` 自訂允許／拒絕 pattern（v0.9）
- Trust Tier、`council trust`、Policy Middleware 完整鏈（v1.0）
- 對 `read_file`／`list_dir`／`read` 類 shell／`run_tests` 要求確認
- 完整 shell AST 解析或跨平台 shell 語義模擬
- 宣稱已具備完整安全機制（確認為操作閘道，分類仍為 pattern 啟發式）

## Capabilities

### New Capabilities

- （無）確認閘道歸入既有 `security` 能力擴充，不另開 capability

### Modified Capabilities

- `security`: 新增互動式確認模式、`--yes`／無 TTY 行為、可注入 confirm 回呼
- `tools`: `run_command` 對 `dangerous`／`write`、以及 `write_file`／`delete_file` SHALL 在副作用前經確認閘道
- `orchestration`: `run_council` SHALL 接受並安裝確認政策（由 CLI 解析 `--yes`／TTY）

## Impact

- **新增**：`src/council_agent/security/confirm.py`；相關測試檔
- **修改**：`tools/shell.py`、`tools/filesystem.py`、`cli.py`、`orchestrator.py`、`security/__init__.py`
- **修改**：`README.md`、`openspec/config.yaml` context（版本號仍為 0.6.0 直至 release bump）
- **依賴**：沿用既有 Rich（無新套件）
- **不變**：CrewAI wrapper 簽名、WorkspaceGuard、分類器 pattern 表、`cli.py` 不直接呼叫 `tools/*`
