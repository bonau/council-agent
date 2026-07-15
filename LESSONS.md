# Lessons Learned

本文件記錄 Council Agent 開發過程中累積的實務經驗，供 AI 協作與後續開發參考，避免重複踩坑。

**硬性規範**（必須遵守）已集中於 [AGENTS.md](AGENTS.md)；本文件說明原因與細節，不作為唯一規範來源。

---

## OpenSpec

### `validate --strict` 需指定範圍

裸跑 `openspec validate --strict` 會回傳 *Nothing to validate*，不代表通過。

```bash
# 驗證進行中的 change
npx @fission-ai/openspec@latest validate --changes --strict

# 驗證已合併至 main specs 的規格
npx @fission-ai/openspec@latest validate --specs --strict
```

發版前兩者都應跑過。

### Artifact 有依賴順序

spec-driven schema 的建議順序：

1. `proposal.md` — 定義 Why、Capabilities（決定要建哪些 `specs/<name>/spec.md`）
2. `design.md` + `specs/**/spec.md` — 可並行，但都依賴 proposal
3. `tasks.md` — 依賴 design 與 specs 完成後才能實作

`applyRequires: ["tasks"]` 表示 tasks 全部勾選完成前，不應宣稱 change 可歸檔。

### Spec delta 格式陷阱

- Scenario 標題**必須**用 `#### Scenario:`（4 個 `#`），用 3 個會 silently fail
- 每個 `### Requirement:` 至少要有 1 個 scenario
- Non-goals 寫在 spec 裡，可避免 scope creep

### 歸檔前先 sync specs

完成實作後的正確收尾順序：

1. 將 delta 合併至 `openspec/specs/<capability>/spec.md`（新增 capability 時含 Purpose 段落）
2. `validate --specs --strict`
3. 將 change 移至 `openspec/changes/archive/YYYY-MM-DD-<name>/`
4. `git add` 時記得 stage 原路徑的 deleted 檔案（git 會辨識為 rename）

---

## Git Flow 與發版

### 標準路徑

```
feature/<name>  ──no-ff──►  develop
                              │
                    release/X.Y.Z  （bump 版本）
                         │    │
                         ▼    └──no-ff──► develop
                        main + tag vX.Y.Z
```

### 版本號要改兩處

發版時同步更新：

- `pyproject.toml` → `[project] version`
- `src/council_agent/__init__.py` → `__version__`

bump 後 `uv lock` / `uv sync` 可能更新 `uv.lock`，一併 commit。

### Commit 拆分建議

依 [CONTRIBUTING.md](CONTRIBUTING.md) 一邏輯一 commit，例如：

```
docs(openspec): add <change> change proposal
feat(<scope>): add core implementation
test(<scope>): add unit tests
chore: release X.Y.Z
```

openspec、feat、test 混在同一 commit 難以 revert。

---

## Tool 模組設計

### 統一 ToolResult，不 raise

所有 tool 的可預期錯誤（檔案不存在、exit code ≠ 0、timeout）都應回傳 `ToolResult(success=False)`，**不要** throw 到 caller。Agent 與 Verification 需要讀結構化失敗結果。

內部 helper `_ok()` / `_err()` 可減少 boilerplate，但**不要** export 至 `__init__.py`。

### 漸進式整合：先函式、後整合

拆成多個里程碑時，建議順序：

1. **純 Python 函式 + 單元測試** — 邏輯可獨立驗證
2. **邊界 / 安全層** — 在函式入口插入，**簽名不變**
3. **框架整合** — 包成 CrewAI `@tool` / `BaseTool`，內部仍呼叫同一套實作

不要在一次 change 裡把上述全部做完；每層應有獨立 spec 與測試。

### run_command 實作細節

- 預設 `timeout_sec` 避免長時間阻塞
- stdout 去掉尾端 `\n` 以保持測試斷言一致
- 非零 exit：`error` 優先放 stderr；無 stderr 時放 exit code 說明
- `metadata` 一律含 `exit_code`、`duration_ms`（含 timeout 失敗）
- `shell=True` 的風險應在 spec / 文件中標示，並由後續安全機制處理

---

## 測試

### 檔案操作：用 `tmp_path`

```python
def test_write_and_read_file(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    ...
```

不要寫死在 repo 內或共用 `/tmp`，避免污染工作區與並行測試衝突。

### Shell 測試：跨平台指令

| 推薦 | 避免 |
|------|------|
| `echo hello` | 平台專用工具或 bash 專用語法 |
| `sys.executable -c "..."` | 假設特定 shell 行為 |
| `timeout_sec` + `time.sleep()` 測 timeout | 依賴外部 `sleep` 指令 |

### 回歸範圍

新增功能測試後，**現有**測試應零修改仍全過——代表 change 沒有意外影響既有管線。

---

## 規劃與協作

### ROADMAP 是 scope 契約

實作前先對照 [ROADMAP.md](ROADMAP.md) 該里程碑的「交付物」與「不做的事」。計畫中的 Non-goals 應寫進 spec，避免：

- 提早做後續里程碑的功能
- 修改不在 scope 內的模組（如 CLI、Orchestrator）

### OpenSpec change 名稱 vs Git 分支

- OpenSpec change：kebab-case、簡短（如 `workspace-guard`）
- Git branch：`feature/<name>`，建議與 ROADMAP 分支名一致

兩者不必完全相同，但應可追溯。

### 發版前 Checklist

- [ ] `uv run pytest` 全過
- [ ] `validate --changes --strict`（歸檔前）或已無 active change
- [ ] `validate --specs --strict`
- [ ] `tasks.md` 全部 `[x]`
- [ ] delta 已 sync 至 `openspec/specs/`
- [ ] change 已 archive
- [ ] `pyproject.toml` + `__init__.py` 版本一致
- [ ] `main` 已 tag、`develop` 已 merge release

---

## 設計假設（需後續驗證）

以下原則應在實作下一層時確認是否仍成立：

- 邊界檢查（如 workspace guard）能否在函式第一行插入，而不改簽名
- 框架 tool 包裝能否直接呼叫底層函式，不需 fork 邏輯
- 高風險操作（如 `shell=True`）是否在文件與 spec 中有明確警示
