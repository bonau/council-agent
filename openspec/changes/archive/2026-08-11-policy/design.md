## Context

v0.8 已有 classifier、確認閘道、審計與 WorkspaceGuard 預設 denylist。ROADMAP v0.9 要求專案根目錄 `council.policy.yaml` 以 Pydantic 驗證並覆寫允許／拒絕指令 pattern 與敏感路徑。約束：`tools/` 禁止 import CrewAI；`cli.py` 禁止直接呼叫 `tools/*`；可預期錯誤回傳 `ToolResult`；不做 Trust Tier／完整 Policy Middleware／hash chain。見 proposal.md 的 Why／Non-goals。

## Goals / Non-Goals

**Goals:**

- 可選 `council.policy.yaml` 載入與嚴格 schema 驗證
- ContextVar 安裝有效政策；shell 指令 deny／allow 評估；路徑 denylist 聯集
- Orchestrator 於 pipeline 期間安裝／重設；缺檔不失敗、壞檔 fail-fast
- 單元與整合測試（`tmp_path`）涵蓋上述行為

**Non-Goals:**

- `trust_tier` 行為、`council trust`、統一 middleware 鏈（v1.0）
- 取代 classifier；政策是額外閘道，不是重寫分類器
- 變更 `.council/config.yaml` 為主要政策來源（保留既有 sandbox 設定；產品政策檔為專案根 `council.policy.yaml`）

## Decisions

### 1. 模組放在 `security/policy.py`

**決策**：政策載入、模型、評估與 ContextVar 皆放 `security/policy.py`，對齊 ROADMAP 套件地圖。

**替代方案**：放 `config/policy.py` — 拒絕，政策屬安全決策層而非一般設定。

### 2. Schema（v0.9 生效欄位）

```yaml
allowed_commands: []   # glob-style patterns; empty/absent = no allowlist
denied_commands: []    # glob-style patterns; hard deny
denied_paths: []       # path patterns merged with DEFAULT_DENIED_PATTERNS
```

**決策**：

- 以 Pydantic `BaseModel` 驗證；未知欄位 `extra="ignore"`，使未來 `trust_tier`／`max_tool_calls` 可出現於檔案而不讓 v0.9 載入失敗，但**不驅動行為**。
- Pattern 比對使用 `fnmatch`（大小寫不敏感），對整段 command 字串；與 ROADMAP 範例 `"pytest *"`／`"curl *"` 一致。
- 不在 v0.9 實作 `max_tool_calls` 政策覆寫（既有 env／settings 機制保留），避免與 orchestration 設定雙來源衝突；若檔案含該欄位則忽略。

**替代方案**：`extra="forbid"` — 拒絕，會阻斷使用者預先放入 v1.0 欄位的政策檔。

### 3. 指令評估順序

**決策**：`denied_commands` → `allowed_commands`（若非空）→ 既有 `classify_command` → 確認閘道 → 執行。

Deny 優先於 allow。Allowlist 僅在列表非空時生效。

**替代方案**：allow 使 dangerous 自動放行 — 拒絕，那是 Trust Tier 語意，屬 v1.0。

### 4. 路徑 denylist 聯集

**決策**：有效 denied paths = `DEFAULT_DENIED_PATTERNS ∪ policy.denied_paths`（去重、保序）。`get_workspace_guard()`（或等價取得點）讀取 ContextVar 中的政策以建構 guard；無政策時行為與今日相同。

**替代方案 A**：政策完全取代預設 — 拒絕，避免使用者漏列 `.env`／`.git` 造成回退。  
**替代方案 B**：同時讀 `.council/config.yaml` 的 `denied_patterns` 並合併 — 可做但不作為本版主路徑；若實作成本低可聯集三者，文件標明 `council.policy.yaml` 為產品政策來源。

### 5. Orchestrator 安裝時機

**決策**：在確認政策與 audit logger 安裝附近，於 crews 執行前 `load_policy_file(project_root)`；缺檔 → 不安裝（defaults）；驗證失敗 → 拋出／回傳錯誤並中止。`finally` 重設 ContextVar。

**替代方案**：lazy load 於第一次 tool 呼叫 — 拒絕，壞檔應 fail-fast，且路徑 guard 在 tool 前就需要一致政策。

### 6. 錯誤呈現

**決策**：政策拒絕經 `ToolResult(success=False, error="… policy …")`；metadata 可含 `policy_decision`（如 `denied`／`not_allowed`）。載入驗證失敗屬 run 級錯誤（非單次 tool）。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Glob 對複雜 shell 字串誤判 | 文件標明啟發式；與 classifier 相同限制 |
| 忽略 `trust_tier` 造成使用者誤解 | README／錯誤訊息說明 v0.9 不生效；v1.0 再接 |
| Guard cache 與政策 ContextVar 不同步 | 安裝／重設政策時清除 `get_workspace_guard` cache，或 guard 每次讀取有效 patterns |
| 測試污染 | 一律 `tmp_path`；預設無政策 |

## Migration Plan

1. 合併後既有專案可選新增 `council.policy.yaml`；缺檔行為不變
2. 發版時再 bump 至 0.9.0（本 change 不 bump 版號）
3. 文件補充政策範例與 Non-goals（無 Trust Tier）

## Open Questions

無（範圍由 ROADMAP v0.9 鎖定；`trust_tier` 忽略策略已於 Decisions #2 定案）。
