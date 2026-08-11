# Council Agent — AI 協作指南

本專案採 **Spec-driven Development（規格驅動開發）**，並以 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理規格與變更。

## 核心原則

1. **先對齊規格，再寫程式** — 功能、修正或重構都應先建立 OpenSpec change，產出 proposal、design、tasks 與 spec delta，經確認後才實作。
2. **規格與程式共存** — `openspec/specs/` 是系統行為的來源真相；`openspec/changes/` 記錄進行中的變更提案。
3. **Delta 優先** — 在既有 codebase 上只描述「新增、修改、移除」的部分，而非重寫整份規格。
4. **實作對照規格** — 完成 tasks 後，Verification 應能對照 spec 中的驗收條件。
5. **ROADMAP 為 scope 契約** — 新 change 的 `proposal.md` **必須**列出 Non-goals，並對齊 [ROADMAP.md](ROADMAP.md) 該里程碑的「不做的事」。

## OpenSpec 工作流程

| 階段 | 指令 | 說明 |
|------|------|------|
| 探索 | `/opsx:explore` | 需求尚不明確時，先釐清選項與取捨 |
| 提案 | `/opsx:propose` | 建立 change 並產生 proposal、design、tasks、spec delta |
| 實作 | `/opsx:apply` | 依 tasks.md 逐步完成，**不可跳步**（見下方漸進式整合） |
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

## 驗證門檻（硬性）

以下情境**必須**通過驗證，才可宣稱 change 完成、開 PR 或發版：

| 時機 | 必跑項目 |
|------|----------|
| 提交／PR 前 | `./scripts/check.sh`（或等價的三項指令） |
| 歸檔前 | sync delta → `validate --specs` → archive |
| 發版前 | 同上 + **不得**有 active change |

```bash
./scripts/check.sh
# 等價於：
# uv run pytest
# npx @fission-ai/openspec@latest validate --changes --strict
# npx @fission-ai/openspec@latest validate --specs --strict
```

**禁止**單跑 `validate --strict`（不含 `--changes` 或 `--specs`）——會回傳 *Nothing to validate*，不代表通過。

完整 checklist 見 [CONTRIBUTING.md](CONTRIBUTING.md) Definition of Done。

## 發版硬性流程

1. **歸檔**：`openspec/changes/` **不得**留有 active change；delta 須先 sync 至 `openspec/specs/`。
2. **版本 bump**：**僅**在 `release/*` 分支更新 `pyproject.toml` 與 `src/council_agent/__init__.py`（兩處必須一致）。
3. **Git flow**：`feature/*` → `--no-ff` merge `develop` → 從 `develop` 開 `release/*` → merge `main` + tag → `--no-ff` merge 回 `develop`。
4. **禁止**：在 `feature/*` 上執行 `chore: release` 或打 release tag。
5. **文件同步**：發版後**必須**更新 `openspec/config.yaml` 版號與 [ROADMAP.md](ROADMAP.md)「現況」段落。

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

- **分支**：`feature/*` 應對應一個 OpenSpec change（名稱建議一致，kebab-case）；完成後 `--no-ff` merge 至 `develop`，**禁止**直接 merge 至 `main`。
- **Commit**：遵循 [CONTRIBUTING.md](CONTRIBUTING.md) 的 conventional commits。
- **測試**：見下方「測試硬性規範」；新功能應在 tasks 中列出對應測試項目。
- **Roadmap**：重大里程碑應先以 OpenSpec change 具體化再開發；實作前對照 ROADMAP 交付物與 Non-goals。

## 套件地圖與模組禁令

```
src/council_agent/
├── cli.py              # Typer CLI 入口
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
├── tools/              # 純 Python tool 函式；回傳 ToolResult
│   ├── base.py         # ToolResult
│   ├── filesystem.py   # read/write/list/delete（經 WorkspaceGuard）
│   ├── shell.py        # run_command、run_tests（經指令分類與政策）
│   └── tracker.py      # ToolCallTracker、max_tool_calls
├── sandbox/
│   └── workspace.py    # WorkspaceGuard 邊界驗證（含政策 denied_paths 聯集）
└── security/           # v0.6+ 安全補強
    ├── classifier.py   # 指令分類（read / write / dangerous）
    ├── confirm.py      # 互動確認閘道
    ├── audit.py        # 結構化審計日誌
    └── policy.py       # council.policy.yaml 載入與評估（v0.9）
```

| 禁令 | 說明 |
|------|------|
| `tools/` **禁止** import CrewAI | 保持可單測的純函式層 |
| `cli.py` **禁止**直接呼叫 `tools/*` | 業務邏輯在 orchestrator / crews |
| Tool 可預期錯誤**禁止** throw | 須回傳 `ToolResult(success=False)` |
| filesystem / shell tool **必須**經 `WorkspaceGuard` | 在函式入口驗證路徑 |
| `run_command` **必須**經指令分類器 | `dangerous`／`write` 經確認閘道（CLI：ask／auto／refuse；函式庫預設 compat） |
| 確認閘道 | `security/confirm.py`；`cli.py` **禁止**直接呼叫 `tools/*`；確認政策經 orchestrator ContextVar |
| 專案政策 | `security/policy.py`；`run_command` 套用 allow/deny；路徑 denylist 與預設聯集 |
| **禁止**宣稱已具完整安全機制 | 分類為 pattern 啟發式；Trust Tier／完整 middleware 見 ROADMAP v1.0 |

## 漸進式整合（硬性）

多層整合（函式 → 邊界 → 框架掛載）的 change **必須**依 `tasks.md` 階段順序實作，**不可跳步**：

1. 純函式／模組 + 單元測試
2. CLI／orchestrator 接線
3. CrewAI `@tool` 包裝與掛載
4. 端對端測試

每階段合併前須 `uv run pytest` 全綠。詳見 [LESSONS.md](LESSONS.md)。

## 測試硬性規範

- 檔案 I/O 測試**必須**使用 pytest `tmp_path`，**禁止**在 repo 內寫入測試產物。
- Shell 測試使用跨平台指令（`echo`、`sys.executable -c`），避免 bash 專用語法。
- `.council/sessions/` **禁止** commit（已在 `.gitignore`）。
- 新增測試後，既有測試**必須**零修改仍全過。

## 不應做的事

- 未建立 change 就直接大規模改動行為或 API。
- 實作完成後不同步更新 spec delta 或 tasks 狀態。
- 在 spec 中描述實作細節（spec 描述「做什麼」，design 描述「怎麼做」）。
- 裸跑 `validate --strict` 並宣稱驗證通過。
- 在 ROADMAP Non-goals 範圍內實作功能（如 v0.5 做指令分類、trust tier）。
- 跳過 `tasks.md` 階段，一次做完多層整合。

## 相關文件

- [CONTRIBUTING.md](CONTRIBUTING.md) — Git Flow、DoD 與 commit 規範
- [ROADMAP.md](ROADMAP.md) — 版本路線圖
- [LESSONS.md](LESSONS.md) — 開發踩坑與實務經驗
- [OpenSpec 文件](https://github.com/Fission-AI/OpenSpec)
