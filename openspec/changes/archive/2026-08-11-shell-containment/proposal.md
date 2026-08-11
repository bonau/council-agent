## Why

v0.9.0 的 shell 邊界會將 classifier 未命中的未知指令預設為 `read`，且以 `shell=True` 執行命令；`run_tests` 也會拆解後重組字串，造成 quoting 漂移與 shell injection 面。v0.9.1 必須先讓分類、政策判斷與實際執行對齊同一個受限 argv action，關閉 V1-001／V1-002，才能安全地繼續 v1.0 前置清債。

## What Changes

- **BREAKING**：未知、無法解析或含 shell metacharacter／複合 shell 語法的命令不再預設為 `read`，而是在建立 subprocess 前 fail-closed，回傳具可測拒絕 metadata 的 `ToolResult(success=False)`。
- 將受支援的簡單命令解析為 argv，並以 `subprocess.run(argv, shell=False)` 執行；v0.9.1 不支援 pipeline、redirect、command substitution 或多命令組合。
- 對至少 `cat`、`ls`、`rm`、`mv`、`cp`、`touch`、`mkdir` 的絕對與相對路徑運算元套用 `WorkspaceGuard`；工作區外、symlink 逃逸或 denied path 在執行前拒絕且不得產生副作用。
- 將 `run_tests` 改為 argv list + `shell=False`，移除 `args.split()` 後拼接 shell 字串的路徑，並保留 policy、classification、confirmation 的等價安全閘道。
- 新增未知／混淆／複合語法、路徑越界、注入、空白與合法特殊字元路徑的單元、整合與無副作用回歸測試。
- 更新 README、known issues 與 v1.0 prep learning log，區分 v0.9.1 已改善的 shell containment 與仍未提供的 OS sandbox／完整安全框架。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `security`: 將命令分類由未知即 `read` 改為明確支援 grammar 的 fail-closed 分類／拒絕契約，並要求 shell metacharacter 與無法解析輸入在執行前拒絕。
- `tools`: 將 `run_command`／`run_tests` 改為 simple argv、`shell=False` 執行，加入 shell 路徑運算元邊界驗證、結構化拒絕 metadata 與無副作用保證。

## Non-goals

- 不實作 Trust Tier 0/1/2，也不啟用 `council trust` 或把 `ConfirmMode`／`--yes` 包裝成 Trust Tier。
- 不建立統一 Policy Middleware／dispatcher 或 `SecurityContext`；該工作屬於 v0.9.2。
- 不提供 OS container、bubblewrap、seccomp、網路隔離或完整作業系統 sandbox。
- 不支援一般用途的複合 shell grammar；v0.9.1 直接拒絕 pipeline、redirect、背景執行、command substitution 與多命令組合。
- 不處理 policy trust boundary、schema version、principal、session authentication、grant 或 audit integrity；各自保留給後續 v0.9.x change。

## Impact

- 受影響程式區域：`src/council_agent/security/classifier.py`、`src/council_agent/tools/shell.py`、`src/council_agent/sandbox/workspace.py`，以及對應 classifier、shell、`run_tests` 測試。
- `run_command(command: str, ...)` 與 `run_tests(path: str, args: str, ...)` 的公開呼叫形狀可維持，但過去依賴 shell expansion、複合語法或未知 executable 的呼叫將改為明確失敗。
- 不新增外部 runtime dependency；使用 Python 標準函式庫的 `shlex` 與 argv subprocess 執行。
- 文件與發行追蹤需同步更新 V1-001／V1-002 的狀態、驗證證據與仍存在的安全限制。
