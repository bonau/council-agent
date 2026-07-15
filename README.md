# Council Agent

OpenRouter + CrewAI 三階段 CLI 框架：每次推論依序經過 **計劃 → 執行 → 校驗** 三個小隊，校驗失敗時由 escalation 角色接手困難段落。

## 功能

- 三階段 Crew 管線（Planning / Execution / Verification）
- 內建兩組模型 Preset，全部透過 OpenRouter 路由
- Typer CLI 介面，支援 `--verbose` 顯示各階段輸出
- 校驗失敗時自動 escalation（可設定 `max_retries`）

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

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `OPENROUTER_API_KEY` | OpenRouter API 金鑰 | （必填） |
| `COUNCIL_DEFAULT_PRESET` | 預設 preset 名稱 | `glm-stack` |

## 開發

本專案採 **Spec-driven Development**，以 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理規格與變更。新功能或修正應先建立 OpenSpec change，對齊規格後再實作。

```bash
uv run pytest
npx @fission-ai/openspec@latest status   # 查看 OpenSpec 變更狀態
```

- [AGENTS.md](AGENTS.md) — AI 協作與 OpenSpec 工作流程
- [CONTRIBUTING.md](CONTRIBUTING.md) — Git Flow 與 commit 規範
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
