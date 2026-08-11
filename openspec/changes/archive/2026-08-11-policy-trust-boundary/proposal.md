## Why

`council.policy.yaml` 目前位於 Agent 可操作的 project workspace，卻缺少 schema version 且會靜默忽略未知安全欄位，容易讓專案政策被誤解為授權來源或讓拼字錯誤的限制失效。v0.9.3 必須先固定 project-owned policy 的 restrict-only 信任邊界，才能在後續版本安全地加入 workspace 外、user-owned 的 trust grant store。

## What Changes

- **BREAKING**：project policy 必須宣告受支援的 `schema_version: 1`；舊版無版本檔、未知版本、未知／拼錯欄位及未來授權欄位一律在 session、crew 或 tool 啟動前 fail-fast，不做部分套用或靜默降級。
- 將 `council.policy.yaml` 定義為 untrusted、project-owned、restrict-only 輸入：`allowed_commands` 只能縮小可接受集合，`denied_commands`／`denied_paths` 只能增加拒絕，不能覆蓋 built-in deny、授予 scope／authentication／grant／tier 或提高信任。
- 讓 `SecurityContext.policy_version` 反映已驗證的 project-policy schema snapshot，而非未版本化暫時 label。
- 將根目錄及巢狀 project 的 `council.policy.yaml` 納入 `WorkspaceGuard` built-in denied paths，使受控 filesystem tool 與已建模 shell path action 無法直接讀寫或刪除政策檔。
- 文件化 v0.9.3 相容性與邊界：policy tool 保護不是 OS sandbox；執行中的惡意專案程式碼、host user 或外部程序仍可能修改 workspace，完整控制面與 user-owned grant store 分別留給後續版本。

## Capabilities

### New Capabilities

無。

### Modified Capabilities

- `security`: 定義 versioned fail-fast schema、restrict-only project-policy 語意及 schema snapshot label。
- `sandbox`: 將 project policy 檔加入不可由受控 filesystem／已建模 shell path action 存取的 built-in denylist。
- `orchestration`: 要求 orchestrator 在建立 session、security context 或 crews 前載入完整且版本相容的 policy，並把 schema version 固定於同一 context snapshot。

## Non-goals

- 不實作 Trust Tier 0/1/2 runtime、`council trust` 或 trust decision matrix。
- 不建立 user-owned grant store；workspace 外的 grant 儲存、grant／revoke lifecycle 留給 v0.9.7。
- 不建立 principal／scope、session authentication、step-up 或任何持久授權來源。
- 不加入 audit hash chain、sequence、redaction 或完整控制面保護；該工作屬 v0.9.4。
- 不提供 OS／container sandbox，也不宣稱可防止 host user、惡意測試程式或任意外部程序修改 policy。
- 不更新 package version；版本 bump 僅在 release branch 進行。

## Impact

- Runtime：`src/council_agent/security/policy.py`、`security/middleware.py`、`sandbox/workspace.py`、`orchestrator.py`。
- Tests：policy schema／migration／restrict-only、middleware snapshot、WorkspaceGuard 與 public tool 無副作用案例。
- Docs/specs：README、security／sandbox／orchestration specs、known issues、learning log、v0.9.x handoff 與 v0.9.3 evidence。
- 使用未版本化 policy 或預先放入 `trust_tier`、`max_tool_calls` 等未知欄位的既有專案必須先遷移，否則 run 將明確拒絕。
