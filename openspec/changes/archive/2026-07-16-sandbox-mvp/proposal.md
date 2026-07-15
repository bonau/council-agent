## Why

Council Agent v0.4 已完成 tool 函式、WorkspaceGuard、tool 追蹤與 Verification 摘要管線，但 Execution Crew 仍未掛載 tools，使用者無法在真實專案目錄讓 Agent 動手 CRUD 檔案並跑 pytest。v0.5 sandbox MVP 需建立 `.council/` 工作區、session 紀錄，並將 tools 整合至 Execution Crew，完成 ROADMAP 的 Tool-First 主線。

## What Changes

- 新增 `council sandbox init` / `council sandbox status` CLI 子命令
- 在 cwd 建立 `.council/config.yaml` 與 `.council/sessions/<id>/` 結構
- Execution Crew 掛載 filesystem / shell tools，並透過 `ToolCallTracker` 記錄每次呼叫
- Session 將 tool 呼叫寫入 `tools.jsonl`，meta 寫入 `meta.json`
- CLI 新增 `--workspace <path>` 指定工作區根目錄
- **不**實作指令分類、互動確認、審計匯出（v0.6+）
- **不**實作 trust tier 或 policy 設定檔（v0.9–v1.0）

## Capabilities

### New Capabilities

（無 — 擴充既有 capability）

### Modified Capabilities

- `sandbox`: 新增 `.council/` 初始化、session 管理與 `council sandbox` CLI
- `tools`: 移除「不整合 Execution Crew」限制；新增 CrewAI tool 掛載需求
- `orchestration`: Execution 階段自動使用 `ToolCallTracker` 並持久化 session 摘要

## Impact

- **修改**：`src/council_agent/cli.py`（sandbox 子命令、`--workspace`）
- **新增**：`src/council_agent/sandbox/session.py`
- **修改**：`src/council_agent/crews/execution.py`（掛載 tools）
- **修改**：`src/council_agent/orchestrator.py`（session 生命週期、tracker 整合）
- **修改**：`README.md`（sandbox 使用說明）
- **新增**：端對端測試（暫存專案目錄完整 run）
