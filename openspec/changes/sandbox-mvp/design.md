## Context

v0.4 提供獨立 tool 函式與 Verification 摘要管線；`ToolCallTracker` 已存在但僅在測試／orchestrator 手動注入。ROADMAP v0.5 要求使用者在任意 cwd 初始化 sandbox，Execution Crew 透過 CrewAI `@tool` 呼叫同一套底層函式，並將紀錄寫入 `.council/sessions/`。

## Goals / Non-Goals

**Goals:**

- `council sandbox init` 建立 `.council/config.yaml`（workspace root、可選 denylist 擴充）
- `council sandbox status` 顯示 workspace root、最近 session、tool 呼叫統計
- Execution Crew 掛載 `read_file`、`write_file`、`list_dir`、`delete_file`、`run_command`、`run_tests`
- 每次 `council run` 建立 session id，tool 呼叫 append 至 `tools.jsonl`
- `--workspace` 覆寫 `COUNCIL_WORKSPACE_ROOT`
- 端對端測試：暫存目錄 init → run（mock LLM）→ 驗證檔案變更與 session 紀錄

**Non-Goals:**

- 指令分類 / 危險指令拒絕（v0.6）
- Rich TUI 確認（v0.7）
- `council audit` 匯出（v0.8）
- Trust tier / policy middleware（v1.0）

## Decisions

### 1. CrewAI tool 包裝

**決策**：在 `tools/crew.py`（或 `execution.py` 同目錄 helper）以 `@tool` 裝飾器包裝既有函式；內部仍呼叫 `filesystem.py` / `shell.py`，並經 `ToolCallTracker.record()`。

**理由**：符合 LESSONS「先函式、後整合」；單一實作來源，避免 fork 邏輯。

### 2. Session 儲存格式

**決策**：

```
.council/sessions/<uuid>/
├── meta.json    # prompt, preset, started_at, workspace_root
└── tools.jsonl  # 每行一筆 {tool, args, success, metadata, timestamp}
```

**理由**：JSONL 易 append、易 tail；meta 與 ROADMAP 一致。

### 3. Sandbox init 行為

**決策**：`sandbox init` 若 `.council/` 已存在則 idempotent 成功（更新 config 若需）；不刪除既有 sessions。

**理由**：避免意外資料遺失；CI 可重複 init。

### 4. Workspace 解析順序

**決策**：`--workspace` CLI 旗標 > `.council/config.yaml` > `COUNCIL_WORKSPACE_ROOT` > `Path.cwd()`。

**理由**：專案級設定優先於程序 cwd；與使用者預期一致。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| v0.5 安全空窗（shell=True 無分類） | README 警示；僅信任目錄使用 |
| CrewAI tool schema 與 Python 簽名不一致 | 薄包裝層只做型別轉換 |
| Session 目錄膨脹 | `.gitignore` 已含 `.council/sessions/` |

## Migration Plan

1. 從 `develop` 開 `feature/sandbox-mvp`
2. 先實作 session + CLI，再掛載 execution tools
3. 既有單元測試零修改仍全過
4. 完成後 archive change → `release/0.5.0`

## Open Questions

（無）
