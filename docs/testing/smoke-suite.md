# v1.0 準備階段 Smoke Suite 設計

> 基線：v0.9.0。狀態：草稿。此 suite 定義 SMK-00～SMK-08 與選配 LIVE-01；公開 beta 前所有必跑案例都必須 PASS，且所有 P0 必須關閉。

## 判定原則

- 結果只使用 `PASS`、`FAIL`、`BLOCKED`、`NOT-RUN`。
- 「成功重現已知缺陷」仍是 `FAIL`，不能標為 PASS 或從分母移除。
- 每個拒絕案例都驗證 exit code、reason、workspace diff 與 outside sentinel 無副作用。
- 證據依 [`v1.0-beta-public-testing.md`](v1.0-beta-public-testing.md) 遮罩；audit 目前沒有可靠 secret redaction，禁止輸入真實秘密。
- shell 目前只驗證 `cwd`，不是真 sandbox；所有案例須在一次性、非特權、無正式資料的環境執行。

## v0.9.0 預期結果

| ID | 主題 | v0.9.0 預期 | 原因 |
|---|---|---|---|
| SMK-00 | 安裝與版本 | PASS | 基線能力 |
| SMK-01 | Sandbox init/status | PASS | 基線能力 |
| SMK-02 | Workspace 內 filesystem CRUD | PASS | 直接檔案工具有 WorkspaceGuard |
| SMK-03 | Path traversal／敏感路徑 | PASS | 直接檔案工具預期拒絕 |
| SMK-04 | Project policy deny | PASS | deny 優先於 allow／confirm |
| SMK-05 | Confirmation／`--yes` | PASS | 可驗證互動語意，但不代表 Trust Tier |
| SMK-06 | Dangerous／未知分類 | **FAIL（預期）** | 未知指令 fail-open 為 `read`，V1-001 |
| SMK-07 | Shell boundary／`run_tests` | **FAIL（預期）** | shell 只驗證 `cwd`；quoting 漂移，V1-001／V1-002 |
| SMK-08 | Audit 顯示與完整性 | **FAIL（預期）** | 無可靠 redaction、sequence、gap 偵測與 hash chain，V1-005 |
| LIVE-01 | 真實 provider 完整管線 | BLOCKED | P0 與離線案例未全過前不執行 |

其中 **SMK-06 與 SMK-07 是目前明確的 shell boundary 預期失敗**。修正版本不得更新表格宣稱 PASS，必須用同一候選 commit 的實際 evidence 取代預期。

## 共用環境與固定順序

1. 建立一次性 VM／容器與非特權使用者。
2. 建立 `$COUNCIL_TEST_ROOT/workspace` 與 `$COUNCIL_TEST_ROOT/outside/sentinel.txt`。
3. 記錄 OS、Python、package version、commit、artifact SHA-256 與 sentinel SHA-256。
4. 預設停用網路，依序執行 SMK-00～SMK-08。
5. 只有全部離線案例 PASS、所有 P0 關閉且 release lead 核准後，才執行 LIVE-01。
6. 保存遮罩後證據，撤銷一次性憑證，驗證 sentinel，再丟棄環境。

## SMK-00 — 安裝、版本與 CLI Help

**目的**：證明候選 artifact 可在乾淨 Python 環境安裝，入口可載入。

**步驟**：

```bash
python -m venv "$COUNCIL_TEST_ROOT/venv"
. "$COUNCIL_TEST_ROOT/venv/bin/activate"
python -m pip install "/path/to/固定的-release-candidate.whl"
council --help
python -m pip show council-agent
```

**斷言**：

- 安裝與 help exit code 為 0。
- 套件版本、wheel SHA-256、commit 與候選 release note 一致。
- 未建立 workspace 外檔案，sentinel 不變。

## SMK-01 — Sandbox Init／Status

**目的**：驗證 sandbox 控制面可在乾淨 workspace 初始化並重入。

**步驟**：

```bash
council sandbox init --workspace "$COUNCIL_TEST_ROOT/workspace"
council sandbox init --workspace "$COUNCIL_TEST_ROOT/workspace"
council sandbox status --workspace "$COUNCIL_TEST_ROOT/workspace"
```

**斷言**：

- 三個命令 exit code 皆為 0。
- `.council/config.yaml` 存在，workspace realpath 正確。
- 重複初始化不覆寫不相關檔案。

## SMK-02 — Workspace 內 Filesystem CRUD

**目的**：驗證直接 filesystem tool 的正向路徑。

**向量**：

- 寫入 Unicode 文字。
- 讀回並比對 byte length／encoding metadata。
- list 結果排序且包含目標。
- 明確 confirmation 後刪除。

**斷言**：所有 `ToolResult` 與實際副作用一致；最後回復初始狀態；sentinel 不變。可直接依 `MAN-02` 執行。

## SMK-03 — Path Traversal、Symlink 與敏感路徑

**目的**：驗證直接 filesystem tools 的 WorkspaceGuard 邊界。

**向量**：

- `../outside/sentinel.txt` read／write。
- workspace 內 symlink 指向 outside 後 read／write。
- `.env`、`.git/`、`.council/secrets/`。
- project policy 新增的 `denied_paths`。

**斷言**：

- 所有拒絕皆 `success=False` 且有可診斷原因。
- 受保護路徑內容、mtime 與 SHA-256 不變。
- 拒絕不建立父目錄或暫存檔。

## SMK-04 — Project Policy 載入與 Deny Precedence

**目的**：驗證 v0.9.0 project policy 的現行限制與 deny 優先序。

**向量**：

- 無政策檔。
- 合法 `allowed_commands`／`denied_commands`／`denied_paths`。
- 型別錯誤與非法 YAML。
- allow 與 deny 同時匹配。
- `ConfirmMode.AUTO` 或 `--yes` 搭配 deny。

**斷言**：

- 合法 allow 成功、deny 失敗且無副作用。
- deny 不能被 confirmation 或 `--yes` 覆蓋。
- 錯誤型別 fail-fast。
- 另記已知限制：project policy 可被 Agent 修改，且未知欄位目前可能被忽略；不得把 policy 當成 grant。

## SMK-05 — Confirmation 與 `--yes` 邊界

**目的**：確認互動方式不被誤當授權。

**向量**：

- TTY `ASK`：選否不執行，選是執行單一預期 action。
- 非 TTY `REFUSE`：write／dangerous 拒絕且無副作用。
- `--yes`：解析為 `ConfirmMode.AUTO`。
- policy deny + `--yes`：仍拒絕。

**斷言**：

- 每次結果有一致 confirmation outcome。
- `ConfirmMode ≠ Trust Tier`；`--yes ≠ 完整授權、principal、authentication 或 grant`。
- 不產生持久授權資料。

## SMK-06 — Dangerous 與未知指令分類

**目的**：驗證已知 dangerous pattern 與未知 shell 語法都 fail-closed。

**向量**：

- 已知 dangerous：`curl`、`sudo`、`chmod`、遞迴／強制 `rm`；用 `REFUSE`，不得真的執行。
- 已知 write：`touch`、`mkdir`、redirect。
- 混合大小寫、前後空白、pipeline、substitution、額外命令。
- 未知 executable 與 `python -c`／`sh -c`。

**Release gate 斷言**：未知、無法解析、混淆及高風險組合一律拒絕；分類與實際執行是同一 canonical action。

**v0.9.0 預期**：未知指令沒有 matched rule 時分類為 `read`，故 **FAIL（V1-001，shell boundary）**。

## SMK-07 — Shell Boundary 與 `run_tests` Quoting

**目的**：證明 shell action 不可越過 workspace，且 pytest action 不受字串重組影響。

**向量**：

- unknown command 使用絕對路徑在 `$COUNCIL_TEST_ROOT/outside/` 建立專用 probe。
- redirect、pipeline、command substitution、子 shell 與額外命令。
- 含空白、Unicode、引號與合法特殊字元的 test path。
- pytest args 中的 shell metacharacter。
- timeout 後確認無殘留程序與副作用。

**Release gate 斷言**：

- outside probe 不建立，sentinel 不變。
- 支援的 pytest argv 正確執行。
- 不支援 shell grammar fail-closed，且沒有檔案、程序或網路副作用。

**v0.9.0 預期**：shell 只驗證 `cwd`，不限制絕對路徑與子程序；`run_tests` 以空白重組 shell 字串。因此 **FAIL（V1-001／V1-002，shell boundary）**。

## SMK-08 — Audit Show、Export、Redaction 與完整性

**目的**：驗證所有產品 tool action 的 audit 可追溯、遮罩且可偵測竄改。

**向量**：

- 成功、policy deny、confirmation refuse、tool error 各一筆。
- 依 session filter show／export，檢查順序與 correlation。
- 只用 `TEST_TOKEN_NOT_A_SECRET_123` 假 marker 測 redaction。
- 刪除一列、重複一列、修改內容、截斷最後一列。
- 嘗試由受控 filesystem／shell action 修改 `.council/audit/`。

**Release gate 斷言**：

- args、metadata、output、error 與巢狀欄位都遮罩。
- sequence、gap、重複、部分寫入與 hash chain 驗證可辨識竄改。
- Agent 無法改寫控制面。
- show／export 不洩漏原始秘密。

**v0.9.0 預期**：show／export 基本功能可用，但 audit 只有截斷，沒有可靠 secret redaction、sequence／gap 驗證或 hash chain。因此 **FAIL（V1-005）**。

## LIVE-01 — 一次性 Provider 憑證完整三階段管線

**預設狀態**：`BLOCKED`；不是一般開發 smoke 的必跑案例。

**解鎖條件**：

- SMK-00～SMK-08 在同一候選 commit 全部 PASS。
- 所有 P0 已關閉。
- release lead 核准。
- 使用可立即撤銷、低額、一次性的 provider key；隔離環境只開必要網域。

**目的**：以最小無害 prompt 驗證 Planning → Execution → Verification 的真實 provider 路徑、session 與 audit correlation。

**安全 prompt**：只要求讀取 workspace 內人工建立的 `sample.txt` 並摘要；第一輪不得要求 shell、寫檔或網路。

**斷言**：

- 三階段完成，最終 verdict 與同一次 attempt 的 output／tool evidence 對應。
- key 不出現在 console、session、audit、exception 或 evidence。
- 沒有 workspace 外副作用。
- 結束後立即撤銷 key 並驗證撤銷。

若要測寫入／確認，須另建已核准向量，不得以 `--yes` 當成完整授權或 authentication。

## Suite 停止與完成條件

任一 P0、越界副作用、policy deny bypass、秘密落盤、audit 無聲損毀或 sentinel 改變都立即停止。公開 beta 的完成條件是 SMK-00～SMK-08 100% PASS、所有 P0 關閉、無 flaky 與無非預期副作用；LIVE-01 是否必跑由 release gate 明確指定。
