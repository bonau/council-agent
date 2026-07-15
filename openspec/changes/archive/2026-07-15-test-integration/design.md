## Context

Council Agent v0.3.0 已完成 WorkspaceGuard 與 filesystem/shell tools。ROADMAP v0.4 要求 Agent 可執行 pytest 並讓 Verification 讀取真實結果。v0.5 才會將 tools 掛載至 Execution Crew；v0.4 先建立 `run_tests`、tool 追蹤基礎設施，並升級 Verification prompt 以接收結構化摘要。

## Goals / Non-Goals

**Goals:**

- 實作 `run_tests(path=".", args="")` 封裝 pytest
- 解析 pytest 輸出，回傳 `metadata`: `exit_code`, `passed`, `failed`, `skipped`, `failures`（失敗摘要列表）
- 實作 `ToolCallTracker`：記錄每次 tool 呼叫、enforce `max_tool_calls`
- 擴充 `ExecutionResult` 攜帶 `tool_summaries: list[ToolCallSummary]`
- Verification prompt 納入 tool 摘要，要求對照 exit code 與 success criteria
- 整合測試：在暫存目錄用真實 tools 產生摘要，mock verification LLM

**Non-Goals:**

- CrewAI Agent tool 掛載（v0.5）
- Session JSONL 紀錄（v0.5）
- 指令分類（v0.6）
- JUnit XML 解析（可選，v0.4 以 pytest 文字輸出 regex 為主）

## Decisions

### 1. pytest 執行方式

**決策**：`run_tests` 內部呼叫 `run_command` 執行 `python -m pytest <path> <args> -q --tb=line`，再解析 stdout/stderr。

**理由**：複用既有 shell tool 與 WorkspaceGuard；`-q` 精簡輸出、`--tb=line` 便於提取失敗行。

### 2. 測試結果解析

**決策**：regex 解析 pytest 摘要行，例如 `3 passed, 1 failed, 2 skipped in 0.12s`；失敗摘要從 `FAILED ...` 或 `E   ...` 行提取。

**理由**：不依賴 pytest-json-report 外掛，保持零額外依賴；跨平台以 `python -m pytest` 為主。

### 3. max_tool_calls 設定來源

**決策**：
- `Settings.max_tool_calls: int = 50`（環境變數 `COUNCIL_MAX_TOOL_CALLS`）
- Preset 可選覆寫 `max_tool_calls`（YAML 欄位，預設 None 表示用 Settings）

**理由**：與 ROADMAP v1.0 policy 範例一致；global default + preset override。

### 4. Tool 追蹤 API

**決策**：`ToolCallTracker` 提供 `record(name, args, result) -> ToolCallSummary | None`；超過上限回傳 `None` 並設定 `limit_reached=True`。Orchestrator 在 v0.4 可手動注入 summaries 至 verification；v0.5 由 execution crew 自動填充。

**理由**：v0.4 先建基礎設施，整合測試以程式化方式呼叫 tools + tracker，不依賴 CrewAI tool loop。

### 5. Verification 輸入格式

**決策**：在 verification task inputs 新增 `{tool_summaries}` 區塊，JSON 序列化 summaries（tool、success、exit_code、passed/failed/skipped）。

**理由**：結構化、可測試；LLM 可對照數字與 plan success criteria。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| pytest 輸出格式因版本而異 | 測試鎖定常見格式；解析失敗時仍回傳 exit_code |
| v0.4 無 crew tool 掛載，摘要來源為手動/測試 | 文件註明 v0.5 才自動填充；整合測試驗證管線 |
| regex 解析不完整 | `failures` 可為空但 exit_code 與計數優先 |

## Migration Plan

1. 從 `develop` 開 `feature/test-integration`
2. 新增 API 向後相容：`ExecutionResult.tool_summaries` 預設空 list
3. v0.5 在 Execution Crew 掛載 tools 並自動使用 tracker

## Open Questions

（無）
