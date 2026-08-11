## Why

v0.8 已具備指令分類、互動確認與審計日誌，但允許／拒絕規則仍硬編碼於 classifier 與 WorkspaceGuard 預設值，專案無法自訂。v0.9 需提供 `council.policy.yaml`，以 Pydantic 驗證並覆寫預設指令 pattern 與敏感路徑，為 v1.0 Trust Tier／Policy Middleware 鋪路。

## What Changes

- 新增 `src/council_agent/security/policy.py`：Pydantic 政策模型、載入／驗證、ContextVar 安裝，以及指令／路徑評估 API
- 專案根目錄可選的 `council.policy.yaml`（允許／拒絕指令 pattern、`denied_paths`）覆寫內建預設
- `run_command` 在分類／確認前套用政策：`denied_commands` 硬拒絕；非空 `allowed_commands` 作為允許清單
- `WorkspaceGuard` 合併政策 `denied_paths`（與預設 denylist 聯集）後再驗證路徑
- Orchestrator 在 pipeline 期間載入並安裝政策；單元／整合測試涵蓋載入、拒絕、允許清單與路徑覆寫
- 更新 README 與 `openspec/config.yaml` context（版號仍為 0.8.0 直至 release bump）

## Non-goals

對齊 ROADMAP v0.9（其餘屬後續里程碑）：

- Trust Tier 0/1/2 行為與 `--trust-tier`（v1.0）
- `council trust` grant／revoke／list（v1.0）
- 完整 Policy Middleware 鏈（分類 → 政策 → 信任 → 審計 → 執行）（v1.0）
- API Key 分級、Session 認證、audit hash chain（v1.0）
- 政策檔中的 `trust_tier` 生效（若出現可驗證後忽略，不驅動行為）
- 遠端／集中式政策派送
- 宣稱已具備完整安全機制（政策為本機覆寫層，分類仍為 pattern 啟發式）

## Capabilities

### New Capabilities

- （無）政策歸入既有 `security` 能力擴充，不另開 capability

### Modified Capabilities

- `security`: 新增政策檔載入／Pydantic 驗證、指令允許／拒絕評估、ContextVar 安裝
- `tools`: `run_command` SHALL 在執行前套用政策允許／拒絕規則
- `sandbox`: `WorkspaceGuard` SHALL 合併政策 `denied_paths` 與預設敏感路徑 denylist
- `orchestration`: `run_council` SHALL 載入並安裝專案政策，並於結束後重設

## Impact

- **新增**：`src/council_agent/security/policy.py`；相關測試；範例／文件中的 `council.policy.yaml`
- **修改**：`tools/shell.py`、`sandbox/workspace.py`（或 guard 取得路徑）、`orchestrator.py`、`security/__init__.py`
- **修改**：`README.md`、`openspec/config.yaml` context（版本號仍為 0.8.0 直至 release bump）
- **依賴**：無新套件（沿用既有 Pydantic + PyYAML）
- **不變**：確認閘道模式、classifier 預設 pattern、審計 JSONL、`cli.py` 不直接呼叫 `tools/*`、Trust Tier
