## Context

Council Agent v0.2.0 已完成 tool 基礎層（`read_file`、`write_file`、`list_dir`、`delete_file`、`run_command`），但無路徑邊界驗證。ROADMAP v0.3 要求所有 tool 操作限制在 workspace root 內。

v0.2 design 預留插入點：在 tool 函式第一行呼叫 `WorkspaceGuard.resolve()`，簽名不變。

## Goals / Non-Goals

**Goals:**

- 實作 `WorkspaceGuard`：`resolve()` 與 `resolve_cwd()`
- 路徑穿越與 symlink 逃逸防護（`Path.resolve()` + root prefix 檢查）
- 預設敏感路徑黑名單：`.env`、`.git/**`、`.council/secrets/**`
- `COUNCIL_WORKSPACE_ROOT` 環境變數（預設 `Path.cwd()`）
- 整合至所有 filesystem 與 shell tools
- 單元測試覆蓋穿越、symlink、黑名單案例

**Non-Goals:**

- CLI `--workspace` 旗標（v0.5）
- `.council/config.yaml` 黑名單擴充（v0.5 / v0.9）
- CrewAI tool 掛載（v0.5）
- 指令分類或危險命令拒絕（v0.6）

## Decisions

### 1. Guard 違規以 Exception 傳遞，tool 轉為 ToolResult

**決策**：`WorkspaceGuardError` 在 guard 層 raise，tool 函式 catch 後回傳 `_err(str(exc))`。

**理由**：保持 guard 邏輯獨立可測；tool 維持「不 raise 可預期錯誤」慣例。

### 2. 路徑解析策略

**決策**：
- 相對路徑：`(root / path).resolve()`
- 絕對路徑：`Path(path).resolve()`
- 邊界：`resolved == root` 或 `resolved.is_relative_to(root)`

**理由**：`resolve()` 展開 symlink 與 `..`，一次處理穿越與 symlink 逃逸。

### 3. 不存在路徑（write 新建）

**決策**：對目標 path 做 `resolve(strict=False)`，檢查 resolved parent 在 root 內，再對目標 relative path 做黑名單檢查。

**理由**：新建檔案時目標尚不存在，但父目錄與 intended path 仍可驗證。

### 4. 黑名單語意

**決策**：
- 直接存取黑名單路徑（read/write/delete/list 目標為 `.env` 等）→ 拒絕
- `list_dir(".")` 列出 `.env` 檔名 → 允許（僅阻擋對敏感路徑本身的操作）
- 比對方式：相對於 root 的 POSIX path，支援 `**` glob（`fnmatch`）

**理由**：平衡安全性與實用性；Agent 需能列出目錄內容但不得讀取敏感檔。

### 5. Singleton 與設定

**決策**：`get_workspace_guard()` 使用 `@lru_cache`，從 `get_settings().council_workspace_root` 建立 guard。

**理由**：避免每次 tool 呼叫重建 guard；與現有 `get_settings()` 模式一致。測試時需 `cache_clear()`。

### 6. run_command cwd 預設

**決策**：`resolve_cwd(None)` 回傳 workspace root。

**理由**：未指定 cwd 時，命令應在 workspace 內執行，與檔案操作邊界一致。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| 既有 tool 測試使用 tmp_path 但 guard 預設 cwd | autouse fixture 設定 `COUNCIL_WORKSPACE_ROOT=tmp_path` |
| `get_settings` / `get_workspace_guard` cache | fixture 內 `cache_clear()` |
| write 不存在路徑邊界判斷複雜 | `resolve(strict=False)` + parent 邊界檢查 |
| macOS `/var` symlink | 測試用 `tmp_path` 自建目錄 |

## Migration Plan

1. 合併 `feature/workspace-guard` → `develop`
2. 既有 tool API 簽名不變；行為變更：拒絕 workspace 外路徑（**行為變更，非 breaking API**）
3. v0.4 在此基礎上加入 `run_tests` 與 Verification 升級

## Open Questions

（無 — ROADMAP 已充分定義 v0.3 範圍）
