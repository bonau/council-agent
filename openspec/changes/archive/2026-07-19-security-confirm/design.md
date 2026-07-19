## Context

v0.6 已在 `run_command` 以指令分類硬拒絕 `dangerous`。ROADMAP v0.7 要求：危險或邊界（寫入）操作觸發 Rich 確認、`--yes` 跳過、無 TTY 預設拒絕。本 change 範圍為選項 3：涵蓋 `dangerous`／`write` shell 與 `write_file`／`delete_file`。

約束：

- `tools/` 禁止 import CrewAI；`cli.py` 禁止直接呼叫 `tools/*`
- 可預期錯誤回傳 `ToolResult(success=False)`，不 raise
- 既有測試在預設政策下須零修改仍全過
- 不做審計、政策檔、Trust Tier

## Goals / Non-Goals

**Goals:**

- 確認模式：`ask`｜`auto`｜`refuse`｜`compat`
- 產品 CLI：TTY→`ask`、`--yes`→`auto`、無 TTY→`refuse`
- 需確認操作：shell `dangerous`／`write`；filesystem `write_file`／`delete_file`
- 拒絕時無副作用；metadata 含 `confirmation`
- 預設 `compat` 維持 v0.6 函式庫行為

**Non-Goals:**

- Audit／policy YAML／trust（v0.8–v1.0）
- 對 read 類操作確認
- 完整 shell 解析

## Decisions

### 1. ContextVar 政策，非函式簽名爆炸

**決策**：`security/confirm.py` 以 `contextvars.ContextVar` 持有 `ConfirmationPolicy`（mode + 可選 `confirm_fn`）。Tools 呼叫 `require_confirmation(action, detail) -> ConfirmationOutcome`；CLI／orchestrator 安裝政策。

**替代方案**：為每個 tool 加 `confirm=` 參數 — 拒絕，因 CrewAI wrapper／tracker 簽名會連鎖變更。

### 2. 四種 ConfirmMode

| Mode | 行為 |
|------|------|
| `compat`（預設） | `dangerous`→拒絕；`write`／filesystem 寫入→允許且不提示 |
| `ask` | 需確認操作呼叫 `confirm_fn`（Rich `Confirm.ask`，default=False）；True 允許、False 拒絕 |
| `auto` | 需確認操作一律允許（`--yes`），不提示；metadata `confirmation=auto` |
| `refuse` | 需確認操作一律拒絕（無 TTY） |

**替代方案**：預設改為 `refuse` — 拒絕，會破壞所有直接呼叫 `write_file`／`mkdir` 的既有測試。

### 3. 閘道掛點

- `run_command`：分類後，若 category ∈ {dangerous, write}（產品模式）或 dangerous（compat），走確認閘道；通過後才 subprocess
- `write_file`／`delete_file`：WorkspaceGuard resolve 成功後、副作用前閘道
- `read_file`／`list_dir`／`read` shell：不經閘道
- `run_tests`：通常為 read；若內部 command 被分為 write／dangerous 則經 `run_command` 閘道

### 4. CLI → orchestrator 接線

**決策**：`cli.run` 新增 `--yes`；以 `sys.stdin.isatty()` 與 `--yes` 解析 mode，傳入 `run_council(..., confirm_mode=...)`。Orchestrator 在 try／finally 設定／重設 ContextVar。Escalation 共用同一政策。

**替代方案**：在 CrewAI tool wrapper 層確認 — 拒絕，因繞過 wrapper 的直接 tool 呼叫會漏閘，且純函式層應可單測。

### 5. metadata 契約

| 結果 | `confirmation` | 其他 |
|------|----------------|------|
| 使用者同意（ask） | `approved` | shell 仍有 classification |
| 使用者拒絕／refuse mode | `denied` 或 `refused` | 無 `exit_code`（shell 未執行） |
| `--yes`／auto | `auto` | 執行後含既有成功／失敗 metadata |
| compat 允許 write | 可省略或 `compat_allow` | 行為同 v0.6 |
| compat 拒 dangerous | `refused`（或沿用無 confirmation 的舊錯誤） | 建議加 `confirmation=refused` 以利一致 |

錯誤訊息須可辨識（含 action／rule／path）。

### 6. Rich Confirm 位置

**決策**：預設 `confirm_fn` 使用 `rich.prompt.Confirm.ask(..., default=False)`，實作於 `security/confirm.py`。測試注入 mock `confirm_fn`。允許 security 層 import Rich；禁止 import CrewAI。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Agent 在 TTY 長跑中多次 pause | 文件說明；CI 用 `--yes`；v1.0 Trust Tier 減少提示 |
| `compat` 與產品行為不一致 | Spec／README 明確區分；CLI 一律安裝產品 mode |
| Confirm 與 CrewAI verbose 輸出交錯 | Prompt 文案簡潔；必要時先停 status spinner（CLI 已有 status context） |
| 既有「dangerous 一律拒」測試語意 | compat 下仍拒；產品 auto／ask 測試另開 |

## Migration Plan

1. 合併後，直接呼叫 tools 的程式碼行為不變（compat）
2. `council run` 預設開始對寫入／危險操作確認；CI／腳本加 `--yes`
3. 發版時再 bump 至 0.7.0（本 change 不 bump 版號）

## Open Questions

無（範圍已由計畫選項 3 鎖定）。
