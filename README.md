# Council Agent

OpenRouter + CrewAI 三階段 CLI 框架：每次推論依序經過 **計劃 → 執行 → 校驗** 三個小隊；校驗失敗時由 escalation 角色修正，並以原成功標準重新校驗。

## 功能

- 三階段 Crew 管線（Planning / Execution / Verification）
- 內建兩組模型 Preset，全部透過 OpenRouter 路由
- Typer CLI 介面，支援 `--verbose`、`--workspace`、`--yes`、`council sandbox` 與 `council audit` 子命令
- 校驗失敗時最多依 `max_retries` escalation；每次修正都有獨立 attempt ID 並重新 Verification，耗盡仍失敗時保持 FAIL
- Tool 基礎層：`read_file`、`write_file`、`list_dir`、`delete_file`、`run_command`、`run_tests`
- Execution Crew 掛載上述 tools，可在工作區內實際改檔與跑測試
- `WorkspaceGuard`：filesystem tools、`run_command` 的 cwd 與受支援命令路徑運算元都驗證工作區、敏感路徑及 symlink 邊界
- 指令分析：明確支援的 simple-command registry 分類為 `read` / `write` / `dangerous`；未知、混淆或無法解析的形式 fail-closed
- 互動確認：危險／寫入 shell 與 `write_file`／`delete_file` 在 CLI 執行時需確認；`--yes` 跳過確認（**不是** Trust Tier 或已驗證授權）；無 TTY 預設拒絕
- 唯一 Policy Middleware：所有 public tool／CrewAI 呼叫經同一 dispatcher 與單一 `SecurityContext`；缺少或已 cleanup 的 context fail-closed
- 結構化審計日誌：sandbox 已初始化時，middleware 對每個 tool action 寫入 redacted、sequenced、canonical-ID 的 correlated attempt／result 至 `.council/audit/events.jsonl`；可用 `council audit show`／`export`（這是 per-event integrity substrate，尚無 predecessor-linked／externally anchored hash chain）
- 專案政策檔：可選根目錄 `council.policy.yaml`，必須使用 `schema_version: 1`；它是 project-owned、restrict-only 輸入，未知／拼錯／授權型欄位與未支援版本會 fail-fast
- Tool 呼叫追蹤與 `max_tool_calls` 上限（預設 50）
- Verification 只使用同一 pipeline attempt 的結構化 tool evidence；成功條件要求 tool／pytest 時，缺少 correlation、exit code 或成功計數不得 PASS
- 可選 `.council/` sandbox：session 紀錄（`meta.json` + `tools.jsonl`）與跨 session 審計（`audit/events.jsonl`）

> **安全提示**：`run_command` 只接受下述受限 simple grammar，並使用 argv + `shell=False`；這是 command boundary 強化，**不是** OS／容器級 sandbox。現有 mandatory dispatcher 已分離 project policy、principal scopes、high-risk step-up authentication、user-owned trust grant store foundation、matrix-v1 decision 與互動確認；但 persisted grant 尚未接到產品 tool，且沒有 Trust Tier 0/1/2 runtime／`--trust-tier`。`council.policy.yaml` 只能加限制；受控 filesystem tools 與已建模 shell path action 預設禁止直接存取控制面。這仍無法阻止 `run_tests` 執行的惡意專案程式碼、host user 或外部程序改檔，audit 也不是 externally anchored hash chain。請僅在信任的專案目錄與可丟棄環境使用。v1.0 前清債與測試文件見 [docs/index.md](docs/index.md)、[ROADMAP.md](ROADMAP.md)。

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

Workspace 解析順序：`--workspace` > `.council/config.yaml` > `COUNCIL_WORKSPACE_ROOT` > 目前工作目錄。未初始化 sandbox 時管線仍會建立 in-memory `SecurityContext`、執行同一 middleware 決策並產生 correlated tracker summaries，但不會建立 session 檔或 durable audit 日誌。

### Policy Middleware 與 library tool API

六個 public tools 與 Execution Crew adapters 都呼叫 `security.middleware.invoke()`。Dispatcher 固定處理 context 驗證、`max_tool_calls`、tool-specific workspace／policy／classification／confirmation、tracker、可選 session、可選 audit，再執行 operation。CrewAI wrapper 只轉接 typed input 與格式化 `ToolResult`，不再自行決定 tracker/session/audit。

直接以 Python 呼叫 public tool 時，caller 必須明確建立並安裝一份 context：

```python
from council_agent.security import SecurityContext, security_context
from council_agent.tools import read_file

context = SecurityContext.create("/path/to/workspace")
with security_context(context):
    result = read_file("README.md")
```

`SecurityContext` 是單次 request snapshot，包含 request/session correlation、workspace guard、project policy snapshot、confirmation policy、tracker，以及可選 session/audit writer。`policy_version` 由 snapshot 推導：缺少 project policy 時是 `builtin`；有效 `schema_version: 1` policy 時是 `project-policy/v1`。Context 會拒絕 policy 與 label 不一致的組合。

若未安裝 context、scope 已 cleanup、copied context 已 stale，public tool 會回傳 `ToolResult(success=False)` 與穩定的 `security_context_*` refusal，不會合成 compat context 或執行 operation。`tools/` 的 underscore helpers 是內部實作且不從 package export；它們不是支援的 product authorization entry。Python 同 process 的 hostile caller 仍可 introspect private objects，因此 middleware boundary 不是 in-process isolation。

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

可在專案根目錄放置可選的 `council.policy.yaml`，於 `council run` 時載入並**增加限制**（缺檔則沿用內建預設）。Project policy 位於 untrusted workspace，只是 restrict-only filter，不是 scope、authentication、grant、Trust Tier 或 confirmation bypass 的授權來源：

```yaml
schema_version: 1

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

Schema version 1 只接受 `schema_version` 與上列三個限制欄位，且型別採 strict validation。缺少／非整數／未支援的 version、未知欄位、拼錯欄位（例如 `denied_command`）及 `trust_tier`、`grant`、`scope` 等授權型欄位都會在 session、context、crew 建立前拒絕整份檔案；不會只套用認得的部分。錯誤會指出檔案與欄位，但不回顯欄位值。

從舊 v0.9 unversioned policy 遷移時，加入 `schema_version: 1`，並移除所有不在範例中的欄位；不提供靜默相容模式。User-owned trust grant store 已使用 workspace 外、不同權限與載入 API 的邊界；project policy 仍不能建立或修改 grant。

`council.policy.yaml` 與巢狀同名 policy 檔預設在 `WorkspaceGuard` denied paths 內，project policy 也不能移除這項 built-in 保護。這會阻擋 public filesystem tools 及受支援、可辨識路徑的 shell action 直接讀寫／刪除政策檔；不代表 OS confinement，尤其 `run_tests` 仍會執行可任意操作 host 權限範圍的專案程式碼。

Policy 在 command analysis 與路徑驗證後、confirmation 前套用。`run_command` pattern 比對 canonical simple command；`run_tests` 的 canonical action 以受信任的目前 Python executable 開頭並包含 `-m pytest`。舊有 `"python -m pytest *"`／`"uv run pytest *"` pattern 不會授權 raw `run_command`（兩者已不在 simple-command registry），需依實際 canonical 表示調整 `run_tests` allowlist。

### Principal 與 tool scopes

`OPENROUTER_API_KEY` 只供 OpenRouter 模型連線使用，不是 Council tool 授權身分。每次 `council run` 會另外建立 local Council principal；可用 `COUNCIL_PRINCIPAL_ID` 指定穩定 ID，未指定時依本機 OS user 產生。Audit/session 只記錄不可逆的 `sha256:` principal reference，不寫入原始 ID 或 provider key。

`COUNCIL_PRINCIPAL_SCOPES` 是逗號分隔的 closed set；未知值會在 pipeline 啟動前拒絕：

| Scope | 允許進入的 action gate |
|------|------|
| `read` | `read_file`、`list_dir`；shell read 另需 `shell` |
| `filesystem:mutate` | `write_file`、`delete_file`；shell write 另需 `shell` |
| `test` | `run_tests`（同時必須有 `filesystem:mutate`，因測試程式可改檔） |
| `shell` | `run_command`（另依 read/write/dangerous 累加 scope） |
| `high-risk:manage` | dangerous shell（同時必須有 `shell` 與 `filesystem:mutate`） |

例如 `COUNCIL_PRINCIPAL_SCOPES=read` 是 read-only principal，不能以 `run_tests`、shell、Crew wrapper、project allowlist 或 `--yes` 間接取得 mutate 權限。Scope decision 每個 action 重新解析；缺 principal、scope 不足、identity mismatch 或 resolver revoke 一律在 tool handler 前 fail closed。

Local principal設定與session UUID本身仍不是authentication。v0.9.6的產品orchestrator會對需要`high-risk:manage`的action要求fresh step-up：`COUNCIL_AUTH_SECRET`作為獨立service/test verifier，產生綁定principal、workspace、runtime session、purpose、exact action與期限的one-use challenge/token。Missing、expired、revoked、replayed或錯綁定proof都在policy／confirmation／handler前fail closed；`--yes`只選confirmation auto，不能取代authentication。

Authentication state只存在process memory，restart會使outstanding challenge/token失效；raw verifier、challenge、response與token不寫入audit、session或console。Direct library `SecurityContext`為相容性預設不啟用step-up requirement，可明確設定`require_high_risk_step_up=True`。

### Trust grant store、decision matrix 與停止線

`council trust grant/revoke/list` 管理 workspace 外的 user-owned schema-v1 store。Store 會驗證 owner-only 權限、non-symlink／workspace non-overlap、strict records、atomic replace 與 persistent revoke；管理操作需要獨立 fresh authentication。這是 grant 管理基礎，不代表產品 tool 已消費 grant。

每個產品 tool action 由 dispatcher 產生 matrix-v1 `trust_decision`，固定依 policy → scope → authentication → grant → risk → interaction 判定，並在 result、tracker、session 與 audit 保留相同 normalized evidence。v0.9.x runtime 固定 grant 為 `trust_grant_not_required`；Tier 0/1/2 source、grant lookup、tier translator 與 `--trust-tier` 只屬後續獨立 v1.0-alpha change。

### Verification／Escalation evidence

Initial execution 與每次 escalation 都有唯一 `pipeline_attempt_id`。同一 attempt 的 output、tool summaries、policy／authorization decisions、test exit code、session／audit correlation 與 Verification verdict 一起保留；escalation 後一定用原 plan／success criteria 重新驗證。`max_retries` 耗盡仍未通過時最終 verdict 保持 FAIL，舊 attempt evidence 不會被新輸出覆寫。

Verification 的 evidence floor 是保守 lexical rule，不是任意語意的形式證明：明確要求 product tool 或 pytest 的 request／plan／success criteria，必須有當次 attempt 的 matching summary；pytest 另須 `exit_code=0`、`failed=0`。純文字任務不會被強制捏造 tool evidence。

## 環境變數

| 變數 | 說明 | 預設 |
|------|------|------|
| `OPENROUTER_API_KEY` | 只供模型連線的 OpenRouter provider API 金鑰 | （必填） |
| `COUNCIL_PRINCIPAL_ID` | Council local principal 穩定 ID（audit 只記遮罩 reference） | 本機 OS user |
| `COUNCIL_PRINCIPAL_SCOPES` | Council tool scopes（逗號分隔、未知值 fail-fast） | 全部五種 scope |
| `COUNCIL_AUTH_SECRET` | High-risk action 的process-local service/test step-up verifier（與`--yes`、provider key、scopes分離） | 未設定；high-risk fail closed |
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
    → Escalation (FAIL 且尚有 retry 時接手)
    → Verification Crew (以同一成功標準重新驗證)
    → Final Output
```

## 授權

MIT
