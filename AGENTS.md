# Council Agent — AI 協作指南

本專案採 **Spec-driven Development（規格驅動開發）**，並以 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理規格與變更。

## 核心原則

1. **先對齊規格，再寫程式** — 功能、修正或重構都應先建立 OpenSpec change，產出 proposal、design、tasks 與 spec delta，經確認後才實作。
2. **規格與程式共存** — `openspec/specs/` 是系統行為的來源真相；`openspec/changes/` 記錄進行中的變更提案。
3. **Delta 優先** — 在既有 codebase 上只描述「新增、修改、移除」的部分，而非重寫整份規格。
4. **實作對照規格** — 完成 tasks 後，Verification 應能對照 spec 中的驗收條件。

## OpenSpec 工作流程

| 階段 | 指令 | 說明 |
|------|------|------|
| 探索 | `/opsx:explore` | 需求尚不明確時，先釐清選項與取捨 |
| 提案 | `/opsx:propose` | 建立 change 並產生 proposal、design、tasks、spec delta |
| 實作 | `/opsx:apply` | 依 tasks.md 逐步實作 |
| 更新 | `/opsx:update` | 需求變更時同步調整 artifacts |
| 歸檔 | `/opsx:archive` | 完成後將 delta 合併至 specs/ |
| 同步 | `/opsx:sync` | 將 specs 與 codebase 對齊 |

CLI 輔助（需 Node.js ≥ 20.19）：

```bash
npx @fission-ai/openspec@latest status
npx @fission-ai/openspec@latest validate --changes --strict
npx @fission-ai/openspec@latest validate --specs --strict
```

常見陷阱與實務經驗見 [LESSONS.md](LESSONS.md)。

## 目錄結構

```
openspec/
├── config.yaml      # 專案脈絡與 schema 設定
├── specs/           # 現行規格（來源真相）
└── changes/         # 進行中的變更提案
    └── <change-name>/
        ├── proposal.md
        ├── design.md
        ├── tasks.md
        └── specs/     # spec delta
```

## 開發慣例

- **分支**：`feature/*` 應對應一個 OpenSpec change（名稱建議一致，kebab-case）。
- **Commit**：遵循 [CONTRIBUTING.md](CONTRIBUTING.md) 的 conventional commits。
- **測試**：Python 專案使用 `uv run pytest`；新功能應在 tasks 中列出對應測試項目。
- **Roadmap**：版本規劃見 [ROADMAP.md](ROADMAP.md)；重大里程碑應先以 OpenSpec change 具體化再開發。

## 套件地圖與模組邊界

```
src/council_agent/
├── cli.py              # Typer CLI 入口；不直接呼叫 tools
├── orchestrator.py     # 三階段管線協調；收集 tool_summaries 傳 Verification
├── types.py            # Plan、ExecutionResult、ToolCallSummary 等共用型別
├── config/
│   ├── settings.py     # 環境變數（含 COUNCIL_MAX_TOOL_CALLS、workspace root）
│   └── presets.py      # YAML preset 載入
├── crews/              # CrewAI 各階段；v0.5 起 execution 掛載 tools
│   ├── planning.py
│   ├── execution.py
│   └── verification.py # v0.4+ 接收 tool 執行摘要
├── llm/
│   └── openrouter.py   # OpenRouter LLM 工廠
├── tools/              # 純 Python tool 函式；回傳 ToolResult，不 raise
│   ├── base.py         # ToolResult
│   ├── filesystem.py   # read/write/list/delete（經 WorkspaceGuard）
│   ├── shell.py        # run_command、run_tests
│   └── tracker.py      # ToolCallTracker、max_tool_calls
└── sandbox/
    └── workspace.py    # WorkspaceGuard 邊界驗證
```

**邊界原則**

- `tools/` 為可重用函式層，**不**依賴 CrewAI；預期錯誤回傳 `ToolResult`，不 throw。
- `sandbox/` 提供邊界驗證；所有 filesystem / shell tool 在入口呼叫 `WorkspaceGuard`。
- `orchestrator.py` 串接 crews 與 tool 摘要；**不**在 CLI 層實作業務邏輯。
- `crews/execution.py` 目前**未**掛載 tools（v0.5 sandbox-mvp 負責整合）。
- `security/` 目錄尚未建立；v0.6+ 依 ROADMAP 新增 policy / audit / trust。

## 不應做的事

- 未建立 change 就直接大規模改動行為或 API。
- 實作完成後不同步更新 spec delta 或 tasks 狀態。
- 在 spec 中描述實作細節（spec 描述「做什麼」，design 描述「怎麼做」）。

## 相關文件

- [CONTRIBUTING.md](CONTRIBUTING.md) — Git Flow 與 commit 規範
- [ROADMAP.md](ROADMAP.md) — 版本路線圖
- [LESSONS.md](LESSONS.md) — 開發踩坑與實務經驗
- [OpenSpec 文件](https://github.com/Fission-AI/OpenSpec)
