## Context

v0.5 已交付 Sandbox MVP：Execution Crew 透過 tools 在 WorkspaceGuard 邊界內操作檔案與執行 shell。`run_command` 仍使用 `shell=True`，任意字串皆可執行。ROADMAP v0.6 要求以指令分類堵住明顯危險操作（`rm -rf`、`sudo`、`curl`、`chmod` 等），作為 v0.7 互動確認與 v1.0 信任框架的第一層。

約束：

- `tools/` 禁止 import CrewAI；分類器為純 Python，可單測
- 可預期錯誤回傳 `ToolResult(success=False)`，不 raise
- v0.6 不做確認 UI、審計、政策檔、Trust Tier
- 既有測試應零修改仍全過（安全指令路徑行為不變）

## Goals / Non-Goals

**Goals:**

- 提供 `classify_command(command: str) -> ClassificationResult`（含 category 與 matched rule）
- 三類：`read`、`write`、`dangerous`；未命中危險／寫入規則者預設 `read`
- `run_command` 在 WorkspaceGuard cwd 驗證之後、subprocess 之前檢查分類；`dangerous` 拒絕執行
- 拒絕時 `metadata` 含 `classification`（與可選 `matched_rule`），且無 `exit_code`（未執行）
- 允許的指令執行後 `metadata` 亦含 `classification`

**Non-Goals:**

- 互動確認、`--yes`、無 TTY 預設（v0.7）
- Audit log / policy YAML / trust grant（v0.8–v1.0）
- 完整 shell 解析（pipe、subshell、編碼繞過等）
- 對 filesystem tools 再分類（已有 WorkspaceGuard）

## Decisions

### 1. 模組位置：`security/classifier.py`

**決策**：新增 `src/council_agent/security/`，與 ROADMAP 目標架構一致。

**替代方案**：放在 `tools/` — 拒絕，因分類是跨 tool 的安全關注點，後續 middleware 會擴充此套件。

### 2. 分類策略：危險優先的 regex pattern 表

**決策**：維護有序列表（dangerous → write → 預設 read）。每條規則為 compiled regex（`re.IGNORECASE`），對**完整指令字串**搜尋。命中第一條危險規則即 `dangerous`；否則命中寫入規則為 `write`；否則 `read`。

**預設危險 pattern（範例，實作可微調但須覆蓋 ROADMAP 範例）：**

| Pattern 意圖 | 範例 |
|--------------|------|
| 遞迴強制刪除 | `rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+.*-r\|-[a-zA-Z]*r[a-zA-Z]*\s+.*-f\|-rf\|-fr)` 等簡化為 `\brm\b` 搭配 `-rf`/`-fr`/`-r`+`-f`，以及 `\bsudo\b`、`\bcurl\b`、`\bwget\b`、`\bchmod\b`、`\bchown\b`、`\bmkfs\b`、`\bdd\b`、`>\s*/dev/`、`\bshutdown\b`、`\breboot\b` |
| 網路／提權 | `curl`、`wget`、`sudo` |
| 權限變更 | `chmod`、`chown` |

簡化實作建議（可維護性優於過度精準）：

```python
DANGEROUS_PATTERNS = [
    (r"\bsudo\b", "sudo"),
    (r"\bcurl\b", "curl"),
    (r"\bwget\b", "wget"),
    (r"\bchmod\b", "chmod"),
    (r"\bchown\b", "chown"),
    (r"\brm\b.*\s-[a-zA-Z]*[rf]", "rm-force-or-recursive"),  # covers -r, -f, -rf, -fr
    (r"\bmkfs\b", "mkfs"),
    (r"\bdd\b", "dd"),
    (r"\bshutdown\b", "shutdown"),
    (r"\breboot\b", "reboot"),
]
```

寫入類（允許執行，標記為 write）：

```python
WRITE_PATTERNS = [
    (r"\bmv\b", "mv"),
    (r"\bcp\b", "cp"),
    (r"\btouch\b", "touch"),
    (r"\bmkdir\b", "mkdir"),
    (r"\btee\b", "tee"),
    (r">\s*\S", "shell-redirect"),  # stdout redirect
]
```

`echo`、`ls`、`cat`、`pytest`、`python -c` 等未命中上述者為 `read`。

**替代方案**：完整 argv 解析 — 延後至 v0.9+；pattern 啟發式符合 ROADMAP「採 pattern 而非完整 shell 解析」。

### 3. `dangerous` 行為：一律拒絕（非確認）

**決策**：v0.6 對 `dangerous` 直接拒絕。確認流程屬 v0.7。

錯誤訊息應清楚標示被拒原因與分類，例如：`Command classified as dangerous (matched: sudo); refused`。

### 4. 接線點：僅 `run_command` 入口

**決策**：在 `run_command` 內、cwd resolve 成功後、`subprocess.run` 前呼叫分類器。`run_tests` 經 `run_command`，pytest 指令通常為 `read`（無危險 token），無需特例。

Filesystem tools 不經分類器。

### 5. API 形狀

```python
class CommandCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"

@dataclass(frozen=True)
class ClassificationResult:
    category: CommandCategory
    matched_rule: str | None = None  # None when default read

def classify_command(command: str) -> ClassificationResult: ...
```

公開於 `council_agent.security`（或 `security.classifier`），供單測與未來 middleware 使用。

### 6. metadata 契約

| 情況 | metadata |
|------|----------|
| 允許並執行 | 既有 `exit_code`、`duration_ms` + `classification`（字串） |
| 危險拒絕 | `classification="dangerous"`、`matched_rule=<id>`；**無** `exit_code` |

### 7. 空／空白指令

**決策**：空白或僅空白字元視為不可執行，回傳 `success=False`（可視為分類前驗證或 `dangerous`／獨立錯誤）。建議：`classify` 回傳 `read` 但 `run_command` 對空指令直接 `_err("Empty command")`，避免啟動 shell。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Pattern 可被繞過（編碼、`$()`、換字元） | 文件標明啟發式；v0.9 政策與 v1.0 middleware 補強；不宣稱完整安全 |
| `\brm\b.*-[rf]` 誤傷 `rm file` 無 flag | 僅擋帶 `-r`/`-f` 的 rm；純 `rm file` 可視為 write 或允許（建議另加 `\brm\b` 為 write，或允許）— 決策：無 force/recursive flag 的 `rm` 歸 `write`（允許），與 ROADMAP「`rm -rf` 危險」一致 |
| `curl` 阻擋合法下載腳本 | 符合 v0.6 預設拒絕；v0.7 確認／v0.9 允許名單解鎖 |
| 既有測試用危險指令 | 盤點測試套件；若有則改為安全指令或改測拒絕路徑 |
| `shell=True` 仍在 | 分類只擋已知 pattern；README 持續警示 |

## Migration Plan

1. 合併後行為變更：過去可執行的 `curl`/`sudo`/`rm -rf` 等會失敗 — **預期的安全強化**，非 API 簽名 breaking
2. 無資料庫／設定檔遷移
3. Rollback：還原 `shell.py` 分類呼叫與移除 `security/` 即可

## Open Questions

（無阻塞項；實作時若某 pattern 誤傷過多合法 pytest／python 指令，可收窄 regex 並補測。）
