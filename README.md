# Council Agent

OpenRouter + CrewAI 三階段 CLI 框架：每次推論依序經過 **計劃 → 執行 → 校驗** 三個小隊，校驗失敗時由 escalation 角色接手困難段落。

## 功能

- 三階段 Crew 管線（Planning / Execution / Verification）
- 內建兩組模型 Preset，全部透過 OpenRouter 路由
- Typer CLI 介面，支援 `--verbose`、`--workspace`、`--yes`、`council sandbox` 與 `council audit` 子命令
- 校驗失敗時自動 escalation（可設定 `max_retries`）
- Tool 基礎層：`read_file`、`write_file`、`list_dir`、`delete_file`、`run_command`、`run_tests`
- Execution Crew 掛載上述 tools，可在工作區內實際改檔與跑測試
- `WorkspaceGuard`：filesystem tools、`run_command` 的 cwd 與受支援命令路徑運算元都驗證工作區、敏感路徑及 symlink 邊界
- 指令分析：明確支援的 simple-command registry 分類為 `read` / `write` / `dangerous`；未知、混淆或無法解析的形式 fail-closed
- 互動確認：危險／寫入 shell 與 `write_file`／`delete_file` 在 CLI 執行時需確認；`--yes` 跳過確認（**不是** Trust Tier 或已驗證授權）；無 TTY 預設拒絕
- 結構化審計日誌：sandbox 已初始化時，CrewAI wrapper 路徑寫入 `.council/audit/events.jsonl`；可用 `council audit show`／`export`（尚無 hash chain／secret redaction）
- 專案政策檔：可選根目錄 `council.policy.yaml`（允許／拒絕指令 pattern、額外敏感路徑）；以 Pydantic 驗證（未知欄位目前會被忽略）
- Tool 呼叫追蹤與 `max_tool_calls` 上限（預設 50）
- Verification 可接收結構化 tool 執行摘要（含 pytest 結果）
- 可選 `.council/` sandbox：session 紀錄（`meta.json` + `tools.jsonl`）與跨 session 審計（`audit/events.jsonl`）

> **安全提示**：`run_command` 只接受下述受限 simple grammar，並使用 argv + `shell=False`；這是 command boundary 強化，**不是** OS／容器級 sandbox。`ConfirmMode`／`--yes` **不等於** Trust Tier。可用 `council.policy.yaml` 限縮規則，但政策檔位於 Agent 可寫的專案目錄。仍**不是**完整信任框架（尚無 Trust Tier、`council trust`、統一 Policy Middleware、principal、hash chain）。請僅在信任的專案目錄與可丟棄環境使用，並避免將不受信任的 prompt 直接餵給 Agent。v1.0 前清債與測試文件見 [docs/index.md](docs/index.md)、[ROADMAP.md](ROADMAP.md)。

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

# 執行完整三階段管線（預設 glm-stack；TTY 下寫入／危險操作會確認）
uv run council run "用 Python 寫一個 FizzBuzz 函式"

# 指定 preset 並顯示各階段輸出
uv run council run "設計 REST API 規格" -p grok-stack --verbose

# CI／非互動環境：跳過確認（無 TTY 時若不加 --yes 會拒絕寫入／危險操作）
uv run council run "跑測試" --yes
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

# 檢視／匯出跨 session 審計日誌（需先 sandbox init）
uv run council audit show
uv run council audit show --session <session-id> --limit 20
uv run council audit export ./audit-export.jsonl
uv run council audit export ./audit-s1.jsonl --session <session-id>
```

Workspace 解析順序：`--workspace` > `.council/config.yaml` > `COUNCIL_WORKSPACE_ROOT` > 目前工作目錄。未初始化 sandbox 時管線仍可執行（向後相容），只是不會寫入 session 檔與審計日誌。

### Shell simple grammar 與 containment

`run_command(command, cwd=...)` 先驗證 cwd，再將輸入以 POSIX-like `shlex` 規則解析一次。只支援一個 simple command：

- read：`echo`、`pwd`、`cat`、`ls`
- write：`rm`、`mv`、`cp`、`touch`、`mkdir`
- dangerous（仍經既有 policy／confirmation）：`sudo`、`curl`、`wget`、`chmod`、`chown`、recursive／force `rm`、`mkfs`、`dd`、`shutdown`、`reboot`

成功分析會產生固定 argv、`classification` 與非空 `matched_rule`。未知 executable、path-qualified executable、shell interpreter、未建模或會混淆路徑語意的 option 會以 `unsupported` 拒絕；空字串、NUL、引號不平衡以 `unparseable` 拒絕；`;`、`|`、`&`、backtick、`$`、`(`、`)`、`<`、`>`、CR／LF 即使在引號內也以 `shell_metachar` 拒絕。拒絕發生在 subprocess 前，沒有 `exit_code`。

`cat`、`ls`、`rm`、`mv`、`cp`、`touch`、`mkdir` 的所有已識別路徑運算元都相對於已驗證 cwd 解析，並在執行前一次驗證；`--` 可標示以 `-` 開頭的路徑。工作區外、denied path 與 symlink escape 分別以 `workspace_boundary`／`denied_path` 拒絕。只有明確建模的 options 可用；需要未建模路徑值的形式（例如 target-directory options）會 fail-closed。

接受的 action 以保留的 argv 呼叫 `subprocess.run(..., shell=False)`，不會重組或再交給 shell 解讀。Project policy 看到的是 `shlex.join(argv)` 產生的穩定 canonical 表示，因此升級後依賴原始空白或不同引號形式的 pattern 可能需要調整。

`run_tests(path, args)` 將已驗證的 `path` 保留成單一 argv element，所以空白、Unicode、引號、`$` 等合法檔名字元不會被 shell 展開。`args` 仍是相容的字串介面，但只解析一次；支援 `-k`、`-m`、`-q`、`-v`／`-vv`、`-x`、`--maxfail`、`--tb`、`--collect-only` 等保守 schema，未知 option、shell control syntax 與不平衡引號會拒絕。測試 action 明確分類為 `write`，並經等價的 project policy 與 confirmation gates。

v0.9.1 的相容性改變是刻意的：任意 executable、`python -c`、`uv run`、shell expansion、redirect、pipeline、command substitution、多命令組合及未建模 options 不再由 `run_command` 執行；pytest 請改用 `run_tests`。

#### 仍存在的安全限制

- 沒有 container、chroot、seccomp、網路隔離、process-tree confinement 或環境變數／`PATH` 隔離。
- 不支援一般 shell grammar；這不是可逃逸或可擴充的 shell parser。
- 已允許且通過 policy／confirmation 的程式仍可能自行存取網路、啟動子程序、解讀檔案或碰觸工作區外資源；argv 安全不等於 hostile-program containment。
- 路徑驗證與程式實際存取間仍有 TOCTOU window；對抗並行惡意檔案系統變更需要 OS 級 containment。
- `run_tests` 會執行專案測試程式碼，並不隔離惡意測試。

### 專案政策檔（`council.policy.yaml`）

可在專案根目錄放置可選的 `council.policy.yaml`，於 `council run` 時載入並覆寫預設規則（缺檔則沿用內建預設；格式錯誤會 fail-fast）：

```yaml
# 非空時作為 shell 指令允許清單（fnmatch，大小寫不敏感）
allowed_commands:
  - "echo *"
  - "* -m pytest *"

# 硬拒絕（優先於 allowlist）
denied_commands:
  - "rm -rf *"
  - "curl *"
  - "sudo *"

# 額外敏感路徑（與內建 .env / .git / .council/secrets 聯集）
denied_paths:
  - "secrets/**"
```

v0.9 生效欄位僅上列三者。檔案中若出現 `trust_tier` 等未來欄位會被忽略且不驅動行為；Trust Tier／`council trust` 見 ROADMAP v1.0。

Policy 在 command analysis 與路徑驗證後、confirmation 前套用。`run_command` pattern 比對 canonical simple command；`run_tests` 的 canonical action 以受信任的目前 Python executable 開頭並包含 `-m pytest`。舊有 `"python -m pytest *"`／`"uv run pytest *"` pattern 不會授權 raw `run_command`（兩者已不在 simple-command registry），需依實際 canonical 表示調整 `run_tests` allowlist。

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
