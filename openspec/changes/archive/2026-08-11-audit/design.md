## Context

v0.7 已有指令分類、確認閘道，以及 sandbox session 的 per-run `tools.jsonl`。ROADMAP v0.8 要求跨 session 的結構化審計日誌與 `council audit show`／`export`。約束：`tools/` 禁止 import CrewAI；`cli.py` 禁止直接呼叫 `tools/*`；可預期錯誤回傳 `ToolResult`；既有測試須零修改仍全過；不做政策檔、Trust Tier、hash chain。

## Goals / Non-Goals

**Goals:**

- Append-only JSONL 審計檔於 `.council/audit/events.jsonl`
- 每筆紀錄含：時間戳、session id（可為 null）、tool 名稱、參數、success／error／精簡 metadata
- Orchestrator 在 sandbox 已初始化時安裝 auditor；Execution tool 路徑寫入審計
- `council audit show` 顯示近期紀錄；`council audit export` 匯出檔案
- 與 session `tools.jsonl` 職責分離（per-run 操作 vs 跨 run 安全軌跡）

**Non-Goals:**

- Hash chain／簽章（v1.0）
- Policy YAML／Trust Tier（v0.9–v1.0）
- 強制審計所有未掛 tracker 的裸 tool 呼叫
- 遠端上傳或集中式 SIEM

## Decisions

### 1. Audit 模組放在 `security/audit.py`，非 sandbox

**決策**：審計屬安全可追溯性，模組放 `security/`；儲存路徑仍在 `.council/audit/`（sandbox 專案目錄）。

**替代方案**：放在 `sandbox/audit.py` — 拒絕，因 ROADMAP 套件地圖將 `audit.py` 列於 `security/`。

### 2. ContextVar 安裝 AuditLogger（對齊 confirm）

**決策**：`AuditLogger` 實例經 `contextvars.ContextVar` 安裝；`record_audit_event(...)` 若無 logger 則 no-op。Orchestrator try／finally 設定／重設。

**替代方案**：僅經函式參數一路傳入 — 拒絕，會讓 tracker／wrappers 簽名膨脹，且與 confirm 模式不一致。

### 3. 寫入掛點：Execution `_invoke`（與 session 並列）

**決策**：在 `crews/execution_tools._invoke` 於 tracker 記錄成功後，若有 auditor 則寫入一筆（含 session_id）。這涵蓋 product 管線所有 tool 呼叫（含確認拒絕後的 `ToolResult`）。

**替代方案 A**：在每個純 tool 函式內寫入 — 過度侵入，且測試會意外產生 audit 檔。  
**替代方案 B**：只在 `ToolCallTracker` — 亦可，但 session_id 不在 tracker；選 `_invoke` 可同時取得 session 與 tracker 結果。

### 4. 儲存格式：單一 append-only `events.jsonl`

**決策**：路徑 `.council/audit/events.jsonl`；每行一個 JSON object。Sandbox `init` 建立 `audit/` 目錄。

**替代方案**：按日切檔 — 延後至用量變大；v0.8 保持單一檔以簡化 show／export。

### 5. 參數截斷與敏感內容

**決策**：字串參數超過固定上限（例如 2 KiB）時截斷並加 `…[truncated]`；`metadata` 只保留可 JSON 序列化的淺層副本。不實作完整秘密掃描（non-goal）。

**替代方案**：完整寫入所有 args — 拒絕，`write_file` content 會讓 audit 膨脹且可能含秘密。

### 6. CLI 行為

| 命令 | 行為 |
|------|------|
| `council audit show` | 讀取 events.jsonl，Rich 表格顯示最近 N 筆（預設 50）；可選 `--session`、`--workspace` |
| `council audit export` | 將紀錄寫出至指定路徑（JSONL 或 JSON array，預設 JSONL）；可選 session 過濾 |

無 sandbox／無 audit 檔時：show 友善提示；export 寫出空集合或錯誤訊息（exit non-zero 僅在路徑無效等硬錯誤）。

### 7. 無 sandbox 的 run

**決策**：若專案未 `sandbox init`，不建立 audit 目錄、不安裝 logger（與現行 session 行為一致）。文件說明：啟用審計需先 init。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Audit 與 session 雙寫重複 | Spec／README 區分職責；audit 跨 session、session 為單次 run |
| 大參數仍佔空間 | 截斷字串；未來可加輪替（非本版） |
| 無 hash chain 可被竄改 | 文件標明；v1.0 補強 |
| 測試污染 repo | 一律 `tmp_path`；預設無 auditor |

## Migration Plan

1. 合併後既有專案需重新 `sandbox init`（idempotent）以建立 `audit/`，或首次寫入時 lazy-create
2. `council run` 在已 init 環境自動寫入 audit；CLI 新增 `audit` 子命令
3. 發版時再 bump 至 0.8.0（本 change 不 bump 版號）

## Open Questions

無（範圍由 ROADMAP v0.8 鎖定）。
