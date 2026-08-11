## Why

v0.7 已具備指令分類與互動確認，但 tool 呼叫仍僅寫入各 session 的 `tools.jsonl`，缺少跨 session、可查詢／可匯出的結構化審計軌跡。v0.8 需補上審計日誌與 `council audit` CLI，讓安全相關操作可追溯，並為 v0.9 政策與 v1.0 Trust Tier／hash chain 鋪路。

## What Changes

- 新增 `src/council_agent/security/audit.py`：結構化 audit record、append-only JSONL logger、ContextVar 安裝／重設
- 所有經 tracker／Execution wrappers 的 tool 呼叫寫入 `.council/audit/events.jsonl`（含時間戳、tool 名稱、參數、結果、session id）
- 新增 `council audit show`／`council audit export` CLI 子命令
- Sandbox init 確保 audit 目錄存在；orchestrator 在 pipeline 期間安裝 audit logger
- 單元／整合測試涵蓋寫入、讀取、匯出與無 sandbox 時的行為
- 更新 README 與 `openspec/config.yaml` context（版號仍為 0.7.0 直至 release bump）

## Non-goals

對齊 ROADMAP v0.8（其餘屬後續里程碑）：

- `council.policy.yaml` 自訂允許／拒絕 pattern（v0.9）
- Trust Tier、`council trust`、Policy Middleware 完整鏈（v1.0）
- Audit log hash chain／防篡改（v1.0）
- 對未經 tracker 的裸 tool 函式呼叫強制審計（函式庫直接呼叫不經 product 管線）
- 遠端集中式 SIEM／雲端審計上傳
- 宣稱已具備完整安全機制（審計為可追溯紀錄，非授權決策層）

## Capabilities

### New Capabilities

- （無）審計歸入既有 `security` 能力擴充，不另開 capability

### Modified Capabilities

- `security`: 新增結構化審計日誌、append-only 儲存、`council audit show`／`export`
- `orchestration`: `run_council` SHALL 在 sandbox 已初始化時安裝 audit logger，並於結束後重設
- `sandbox`: init／目錄結構 SHALL 包含 audit 儲存路徑；與 session `tools.jsonl` 區分職責

## Impact

- **新增**：`src/council_agent/security/audit.py`；相關測試；CLI `audit` 子命令群
- **修改**：`crews/execution_tools.py` 或 tracker、`orchestrator.py`、`cli.py`、`sandbox/config.py`、`security/__init__.py`
- **修改**：`README.md`、`openspec/config.yaml` context（版本號仍為 0.7.0 直至 release bump）
- **依賴**：無新套件（JSONL + 既有 Rich／Typer）
- **不變**：確認閘道、指令分類、WorkspaceGuard、`cli.py` 不直接呼叫 `tools/*`、session `tools.jsonl` 仍為 per-run 操作紀錄
