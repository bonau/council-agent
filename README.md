# Council Agent

OpenRouter + CrewAI 三階段 CLI 框架：每次推論依序經過 **計劃 → 執行 → 校驗** 三個小隊，校驗失敗時由 escalation 角色接手困難段落。

## 功能

- 三階段 Crew 管線（Planning / Execution / Verification）
- 內建兩組模型 Preset，全部透過 OpenRouter 路由
- Typer CLI 介面，支援 `--verbose`、`--workspace` 與 `council sandbox` 子命令
- 校驗失敗時自動 escalation（可設定 `max_retries`）
- Tool 基礎層：`read_file`、`write_file`、`list_dir`、`delete_file`、`run_command`、`run_tests`
- Execution Crew 掛載上述 tools，可在工作區內實際改檔與跑測試
- `WorkspaceGuard` 限制檔案與 shell 操作在工作區內
- Tool 呼叫追蹤與 `max_tool_calls` 上限（預設 50）
- Verification 可接收結構化 tool 執行摘要（含 pytest 結果）
- 可選 `.council/` sandbox：session 紀錄（`meta.json` + `tools.jsonl`）

> **安全提示**：`run_command` 使用 `shell=True` 執行指令，且 v0.5 **尚無**指令分類或互動確認。請僅在信任的專案目錄使用，並避免將不受信任的 prompt 直接餵給 Agent。完整安全機制（指令分類、信任階梯、審計）規劃見 [ROADMAP.md](ROADMAP.md) v0.6+。

## Presets

### `glm-stack`

| 角色 | 模型 |
|------|------|
| 計劃 | `z-ai/glm-5.2` |
| 執行 | `deepseek/deepseek-v4-flash` |
| 校驗 | `openai/gpt-5.6-luna` |
| 升級 | `openai/gpt-5.6-luna` |

### `grok-stack`

| 角色 | 模型 |
|------|------|
| 計劃 | `x-ai/grok-4.5` |
| 執行 | `deepseek/deepseek-v4-flash` |
| 校驗 | `google/gemini-3.5-flash` |
| 升級 | `x-ai/grok-4.5` |

> Composer 2.5 為 Cursor 專屬模型，無法經 OpenRouter 呼叫；`grok-stack` 執行層改用 DeepSeek V4 Flash。

## 安裝

```bash
uv sync --extra dev
cp .env.example .env
# 編輯 .env，填入 OPENROUTER_API_KEY
```

## 使用

```bash
# 列出可用 preset
uv run council presets list

# 執行完整三階段管線（預設 glm-stack）
uv run council run "用 Python 寫一個 FizzBuzz 函式"

# 指定 preset 並顯示各階段輸出
uv run council run "設計 REST API 規格" -p grok-stack --verbose
```

### Sandbox 工作流程

在專案目錄初始化後，Execution Crew 會掛載 tools；有 `.council/` 時每次 `run` 會寫入 session。

```bash
# 在目前專案目錄初始化 sandbox（idempotent，不刪既有 sessions）
uv run council sandbox init

# 帶 tools 執行完整管線（可覆寫工作區根目錄）
uv run council run "為 utils.py 補上測試並確保 pytest 通過" --verbose
uv run council run "整理 README" --workspace /path/to/project

# 查看工作區與最近 session 摘要
uv run council sandbox status
```

Workspace 解析順序：`--workspace` > `.council/config.yaml` > `COUNCIL_WORKSPACE_ROOT` > 目前工作目錄。未初始化 sandbox 時管線仍可執行（向後相容），只是不會寫入 session 檔。

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `OPENROUTER_API_KEY` | OpenRouter API 金鑰 | （必填） |
| `COUNCIL_DEFAULT_PRESET` | 預設 preset 名稱 | `glm-stack` |
| `COUNCIL_WORKSPACE_ROOT` | Tool 工作區根目錄 | 目前工作目錄 |
| `COUNCIL_MAX_TOOL_CALLS` | 單次 run 的 tool 呼叫上限 | `50` |

## 開發

本專案採 **Spec-driven Development**，以 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理規格與變更。新功能或修正應先建立 OpenSpec change，對齊規格後再實作。

環境需求：Python 3.11+（uv）、Node.js ≥ 20.19（OpenSpec CLI）。

```bash
./scripts/check.sh   # 提交／PR 前必跑：pytest + openspec validate
npx @fission-ai/openspec@latest status   # 查看 OpenSpec 變更狀態
```

硬性規範（模組邊界、發版流程、驗證門檻）見 [AGENTS.md](AGENTS.md)。

- [AGENTS.md](AGENTS.md) — AI 協作與硬性開發規範
- [CONTRIBUTING.md](CONTRIBUTING.md) — Git Flow、DoD 與 commit 規範
- [ROADMAP.md](ROADMAP.md) — 版本路線圖

## 架構

```
User Prompt
    → Planning Crew   (結構化計劃)
    → Execution Crew  (依計劃執行)
    → Verification Crew (PASS / FAIL)
    → Escalation (FAIL 時接手)
    → Final Output
```

## 授權

MIT
