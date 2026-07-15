## Context

Council Agent v0.1.0 已完成三階段管線（Planning → Execution → Verification → Escalation），但 Execution Crew 僅產出文字。ROADMAP 採 Tool-First 漸進式策略：v0.2 建立 tool 基礎層，v0.3 加入 WorkspaceGuard，v0.5 才掛載至 Execution Crew。

現有程式碼慣例：`@dataclass` 型別（`types.py`）、pytest + `tmp_path` 測試、標準庫優先、無額外依賴。

## Goals / Non-Goals

**Goals:**

- 建立 `ToolResult` 統一回傳結構
- 實作 5 個純 Python tool 函式（filesystem × 4、shell × 1）
- 所有可預期錯誤轉為 `ToolResult(success=False)`，不 raise
- 單元測試覆蓋成功與失敗路徑
- 預留 v0.3 guard 插入點（函式簽名不變）

**Non-Goals:**

- WorkspaceGuard / 路徑邊界驗證（v0.3）
- `run_tests` tool（v0.4）
- CrewAI `@tool` / `BaseTool` 包裝（v0.5）
- CLI、Orchestrator、Execution Crew 變更
- 指令分類或安全 middleware（v0.6+）

## Decisions

### 1. 純函式 API，非 CrewAI Tool 子類

**決策**：v0.2 提供 `(path, ...) -> ToolResult` 純函式，v0.5 再包裝為 CrewAI tool。

**理由**：v0.2–v0.4 需獨立測試 tool 邏輯；CrewAI 包裝增加耦合且非本版需求。

**替代方案**：直接實作 `BaseTool` 子類 — 拒絕，因 v0.3 guard 需包裝同一邏輯，純函式更乾淨。

### 2. 錯誤不 raise，回傳 ToolResult

**決策**：檔案不存在、權限不足、目錄非檔案等 → `success=False, error="..."`。

**理由**：Agent 需讀取結構化失敗結果；raise 會中斷 crew 流程。

### 3. write_file 自動建立父目錄

**決策**：`Path(path).parent.mkdir(parents=True, exist_ok=True)` 後寫入。

**理由**：Agent 建立 nested 檔案是常見操作；v0.5 sandbox 場景需要。

### 4. run_command 使用 shell=True，預設 timeout 120 秒

**決策**：`subprocess.run(..., shell=True, timeout=120)`，metadata 含 `exit_code` 與 `duration_ms`。

**理由**：Agent 需執行複合指令（如 `uv run pytest`）；v0.6 才加入指令分類。timeout 防止無限阻塞。

**替代方案**：`shell=False` + shlex — 彈性不足，v0.6 前可接受風險。

### 5. 內部 helper `_ok` / `_err`

**決策**：`base.py` 提供模組內 helper，不 export 至 `__init__.py`。

**理由**：減少各 tool 重複 boilerplate，保持公開 API 精簡。

### 6. 模組拆分

**決策**：`base.py`（ToolResult）、`filesystem.py`（4 tools）、`shell.py`（run_command）。

**理由**：對齊 ROADMAP 目標架構；v0.4 在 `shell.py` 加 `run_tests` 不需動 filesystem。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| v0.2 無路徑防護，可存取 cwd 外路徑 | spec 與文件標示 Non-goal；僅用於開發/測試；v0.3 優先接續 |
| `run_command` shell=True 命令注入 | v0.2 不掛載 Agent；v0.6 指令分類 |
| 跨平台 shell 測試不穩定 | 測試用 `python -c` / `echo` 等可攜指令 |

## Migration Plan

1. 合併 `feature/tools` → `develop`
2. 無 breaking change（新增模組，不修改現有 API）
3. v0.3 在 tool 函式開頭插入 `WorkspaceGuard.resolve()`，簽名不變

## Open Questions

（無 — ROADMAP 已充分定義 v0.2 範圍）
