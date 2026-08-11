# v1.0 發行準備學習紀錄

- 建立日期：2026-08-11
- 探索基準：v0.9.0，commit `c5e77cb2598dc17c88031aec47bbaaff5da1c24b`
- 狀態：初稿；供 v0.9.x patch 規劃與 v1.0-alpha 准入判斷
- 配套 playbook：`docs/releases/major-release-prep-playbook.md`

> 本紀錄描述發行前發現與後續驗收方向，不代表問題已修正。
>
> **本準備工作不實作 Trust Tier 本體。Trust Tier 0/1/2 的 runtime 行為、對外 CLI 與完整授權整合屬於 v1.0-alpha。**

## 探索範圍與判讀方式

2026-08-11 依序對照：

1. `ROADMAP.md` 的 v1.0 承諾與 Definition of Done。
2. `openspec/specs/` 的 security、tools、sandbox、orchestration 現行規格。
3. `openspec/changes/archive/` 中 classifier、confirmation、audit、policy 的設計決策與 Non-goals。
4. `src/council_agent/` 的實際安全入口、ContextVar、tool wrapper、session、Verification 與 Escalation。
5. `tests/`、README、AGENTS、CONTRIBUTING 與 LESSONS 的測試覆蓋及對外說法。

判讀原則：

- ROADMAP 是 scope 契約，main specs 是現行行為的規格來源真相，archive 是歷史決策脈絡，程式與執行證據代表實況。
- 任兩者不一致即列為衝突，不採用最樂觀解讀。
- 安全宣稱必須同時有拒絕案例、旁路案例與無副作用證據。
- P0／P1 全部關閉前，不得進入 v1.0-alpha。

## 已確認的正向基線

- `WorkspaceGuard` 會對直接 filesystem tool 做 workspace、path traversal、symlink 與敏感路徑檢查。
- `run_command` 目前有 project policy、classifier 與 confirmation gate，政策 deny 優先於 allow。
- 已知型別錯誤的 `council.policy.yaml` 會在 crews 執行前 fail-fast。
- README 已警示 `shell=True`、pattern classifier 與尚無完整 Trust Tier／Policy Middleware／hash chain。
- v0.9.0 的 `pyproject.toml` 與 `src/council_agent/__init__.py` 版本一致。

上述基線不能抵銷後述旁路與信任邊界問題。

## 2026-08-11 P0–P2 問題摘要

| ID | 等級 | 摘要 | 主要證據 | 建議版本 |
|---|---|---|---|---|
| V1-001 | P0 | classifier 未命中 pattern 時預設為 `read`；啟發式字串比對無法證明命令安全，複合 shell 語法仍可能以低風險身分執行 | `security/classifier.py`、`tools/shell.py` | v0.9.1 |
| V1-002 | P0 | `run_tests` 以 `args.split()` 後再用空白拼成字串交給 `shell=True`；路徑空白、引號、metacharacter 會造成語意漂移或注入面 | `tools/shell.py` | v0.9.1 |
| V1-003 | P0 | 沒有唯一 dispatcher；政策、確認、tracker、session 與 audit 分散。audit 只在 Execution Crew `_invoke`，直接 tool 呼叫不留安全 audit | `tools/*`、`crews/execution_tools.py`、`orchestrator.py` | v0.9.2 |
| V1-004 | P1 | 專案內政策檔與使用者授權邊界尚未分離；schema 無版本且 `extra="ignore"`，未知安全欄位會被靜默忽略，未來可能造成錯誤信任期待 | `security/policy.py`、policy archive design | v0.9.3 |
| V1-005 | P1 | audit 位於 workspace 內，沒有完整控制面保護；只有截斷，沒有欄位型 redaction、sequence／gap 驗證與可靠完整性基礎 | `security/audit.py`、`sandbox/workspace.py` | v0.9.4 |
| V1-006 | P1 | `api_key` 是 LLM provider credential，不是授權 principal；系統沒有 read-only／mutate／shell 等可驗證 scope 模型 | `orchestrator.py`、`llm/openrouter.py` | v0.9.5 |
| V1-007 | P1 | session UUID 只做紀錄識別，沒有 authentication、到期、重放防護或高權限 step-up 證據 | `sandbox/session.py`、`orchestrator.py` | v0.9.6 |
| V1-008 | P1 | 尚無使用者擁有、workspace 外、可 revoke 且綁定 principal 的 trust grant store | ROADMAP v1.0；目前程式無對應模型 | v0.9.7 |
| V1-009 | P1 | `ConfirmMode.AUTO` 目前可直接允許需確認操作；互動方式與授權來源混在一起，不能直接映射成 Trust Tier | `security/confirm.py`、CLI mode resolution | v0.9.8 |
| V1-010 | P1 | Verification FAIL 後的 Escalation 產生新輸出，但沒有再次 Verification；回傳 verdict 仍是舊輸出的 verdict，tool evidence 也未閉合 | `orchestrator.py` 的 `run_escalation`／`run_council` | v0.9.9 |
| V1-011 | P2 | 尚無真人與 Agent 分離的可重現發行測試手冊；ROADMAP、spec、archive 與 README 的完成／延期語意需要逐項校正 | 發行文件與測試文件缺口 | v0.9.9 |

## 固定子版本序列

此序列為本次探索的採用決策，不得因實作方便任意合併：

1. v0.9.1 Shell containment（含 classifier fail-open 與 `run_tests` quoting）
2. v0.9.2 唯一 Policy Middleware／dispatcher + `SecurityContext`
3. v0.9.3 政策 trust boundary + versioned schema fail-fast
4. v0.9.4 Audit integrity substrate（控制面保護、redaction、sequence）
5. v0.9.5 Principal／API Key scope 模型
6. v0.9.6 Session authentication foundation
7. v0.9.7 User-owned trust grant store
8. v0.9.8 Trust Tier decision matrix（與 `ConfirmMode` 分離）
9. v0.9.9 Verification／escalation evidence closure + 文件校正

每版只處理一個主要問題；必要 spec、測試與直接相關文件可隨版更新。Trust Tier runtime 本體仍留在 v1.0-alpha。

## v0.9.1 — Shell containment

- **問題 / 為何阻斷 v1.0**
  - `classify_command()` 未命中 dangerous／write pattern 時直接回傳 `read`。這是「未知即允許」的 fail-open，不足以支撐後續信任階梯。
  - `run_command()` 使用 `shell=True`；只驗證 cwd 在 workspace 內，不代表 command 的檔案、子程序、redirect 或網路副作用被限制在 workspace。
  - `run_tests()` 將已解析路徑與 `args.split()` 結果重新用空白拼成 shell 字串。合法的空白／引號可能壞掉，惡意 metacharacter 可能改變執行語意。
  - 若底層執行語意不穩定，後續 policy、grant 與 tier 都可能授權到與畫面不同的動作。
- **涉及模組**
  - `src/council_agent/security/classifier.py`
  - `src/council_agent/tools/shell.py`
  - `src/council_agent/sandbox/workspace.py`
  - `openspec/specs/security/spec.md`
  - `openspec/specs/tools/spec.md`
  - `tests/test_command_classifier.py`
  - `tests/test_run_command_classification.py`
  - `tests/test_tools_run_tests.py`
- **驗收條件**
  - 支援的 command grammar、組合運算子與不支援語法有明確規格；未知、無法解析、混淆或高風險組合一律 fail-closed。
  - command 的分類／政策判斷與實際執行使用同一個 canonical action，不會先檢查 A、實際執行 B。
  - `run_tests` 不經不安全的 shell 字串重組；含空白、Unicode、引號與合法特殊字元的路徑可正確執行。
  - pytest 參數有明確解析規則；metacharacter、command substitution、redirect 與額外命令不能注入。
  - cwd、path traversal、symlink、外部 sentinel 與環境繼承有拒絕測試；拒絕後無檔案、程序或網路副作用。
  - README 與 spec 明確說明 containment 保證及未保證項目，不把 pattern classifier 描述成完整 sandbox。
- **Non-goals**
  - 不建立統一 dispatcher／`SecurityContext`；留到 v0.9.2。
  - 不加入 policy schema version、principal、session authentication、grant 或 Trust Tier。
  - 不擴充一般用途 shell 功能；安全性優先於接受所有 shell 語法。
- **學習紀錄應補記什麼**
  - 原始繞過案例、canonical action 選擇、被拒絕語法清單與相容性影響。
  - 每個拒絕案例的外部 sentinel、exit code、metadata 與「無副作用」證據。
  - `run_tests` 在空白／特殊字元路徑的 smoke 結果。
  - 尚未納入支援的 shell 語法及後續責任版本。

## v0.9.2 — 唯一 Policy Middleware / dispatcher + SecurityContext

- **問題 / 為何阻斷 v1.0**
  - 現行安全檢查散落在 shell、filesystem、Crew wrapper 與 orchestrator；沒有可證明「所有產品 tool 呼叫都經過」的唯一 choke point。
  - audit 只在 Execution Crew `_invoke` 寫入；直接呼叫純 tool 會繞過 tracker、session 與 audit。未來 Trust Tier 若只掛其中一層也會出現同類旁路。
  - 多個獨立 ContextVar 無法作為一次決策的完整、不可混用 context。
- **涉及模組**
  - `src/council_agent/security/` 下的 middleware／context 責任
  - `src/council_agent/tools/filesystem.py`
  - `src/council_agent/tools/shell.py`
  - `src/council_agent/crews/execution_tools.py`
  - `src/council_agent/tools/tracker.py`
  - `src/council_agent/orchestrator.py`
  - `src/council_agent/types.py`
  - tools、security、orchestration main specs 與旁路整合測試
- **驗收條件**
  - 每個產品 tool 呼叫只有一個 dispatcher 入口，固定執行 context 驗證、政策／授權決策、追蹤、審計與實際執行。
  - `SecurityContext` 有 request／session 關聯、workspace、政策版本與後續 principal／authentication／grant 可擴充欄位；一次呼叫只使用同一份 snapshot。
  - CLI、Crew wrapper、Escalation 與 library 的產品路徑都通過 dispatcher；旁路測試可證明無第二條可執行路徑。
  - 缺少、過期、錯配或解析失敗的 context fail-closed，並產生可診斷的拒絕事件。
  - 被 policy 拒絕、超過 tool limit、執行失敗與成功都使用一致的 event／summary 關聯 ID。
  - `run_tests` 等複合 tool 不重複授權或重複 audit，且子動作關係可追溯。
- **Non-goals**
  - 不決定 project policy 的信任來源與 schema 版本；留到 v0.9.3。
  - 不完成 principal scope、session authentication、grant 或 Trust Tier 語意。
  - 不讓 `tools/` import CrewAI；wrapper 仍留在 `crews/`。
- **學習紀錄應補記什麼**
  - 完整入口清單、刪除／封閉的旁路、dispatcher 不變量與 context 欄位責任。
  - 每條產品路徑對同一 action 產生相同 decision／audit 的證據。
  - context 缺失、巢狀呼叫、例外與 reset 的回歸結果。
  - 暫時保留的低階 API 及其「非產品授權入口」限制。

## v0.9.3 — 政策 trust boundary + versioned schema fail-fast

- **問題 / 為何阻斷 v1.0**
  - `council.policy.yaml` 位於 Agent 可操作的專案邊界內；它可以增加限制，但不得在 v1.0 被誤用為授權或提升信任的來源。
  - 現行 model 使用 `extra="ignore"` 且沒有 `schema_version`。拼錯、未支援或未來安全欄位會被靜默忽略，使用者可能以為控制已生效。
  - Trust Tier 前必須先分清楚「專案可自我限縮」與「使用者可授權」兩個 trust boundary。
- **涉及模組**
  - `src/council_agent/security/policy.py`
  - `src/council_agent/orchestrator.py`
  - `src/council_agent/sandbox/workspace.py`
  - `council.policy.yaml` 範例、README 與 migration 文件
  - security、sandbox、orchestration main specs
  - `tests/test_policy.py`、`tests/test_run_command_policy.py`
- **驗收條件**
  - policy 有必填、可辨識的 `schema_version`，並有版本相容／遷移規則。
  - 未知欄位、拼錯欄位、未支援版本與不合法組合在建立 session／執行 tool 前 fail-fast，不套用部分政策。
  - project policy 明確是 untrusted、restrict-only；無法授予 scope、authentication、grant、tier 或取消 built-in deny。
  - 使用者擁有的授權資料與 workspace policy 使用不同儲存邊界、權限與載入 API。
  - 錯誤訊息指出檔案、schema version 與欄位，但不洩漏秘密。
  - 舊 v0.9 policy 有可測試的遷移與拒絕策略，沒有靜默降級。
- **Non-goals**
  - 不建立 principal、session authentication 或 user-owned grant store。
  - 不啟用 `trust_tier` 欄位或 Trust Tier runtime 行為。
  - 不提供遠端集中式政策服務。
- **學習紀錄應補記什麼**
  - 採用的 schema version、相容矩陣、舊檔遷移結果與拒絕範例。
  - project policy 可限縮／不可授權的欄位清單。
  - 未知欄位 fail-fast 對既有使用者的影響與 release note。
  - policy root、workspace root、user-owned root 的實際邊界證據。

## v0.9.4 — Audit integrity substrate

- **問題 / 為何阻斷 v1.0**
  - audit 寫在 `.council/audit/`，但現有 denylist 沒有把整個控制面視為受保護資源；具 workspace 寫入能力的 Agent 可能改寫或刪除安全證據。
  - 現行只截斷長字串，沒有依欄位／內容類型做秘密 redaction；session log 也可能保留完整 args、output 與 error。
  - event 沒有 sequence、穩定 event ID、gap／重複檢查與 canonical integrity envelope，無法可靠建立 v1.0 hash chain。
- **涉及模組**
  - `src/council_agent/security/audit.py`
  - `src/council_agent/sandbox/session.py`
  - `src/council_agent/sandbox/workspace.py`
  - `src/council_agent/sandbox/config.py`
  - dispatcher／`SecurityContext`
  - `src/council_agent/cli.py` 的 audit show／export 邊界
  - audit、sandbox、orchestration specs 與測試
- **驗收條件**
  - audit、authentication、grant 等控制面路徑預設不可由受控 Agent 的 filesystem 或 shell action 修改。
  - args、metadata、output、error 與巢狀結構共用明確 redaction 規則；API key、token、passphrase 與常見秘密格式不落盤。
  - 每筆 event 有單調 sequence、穩定 ID、session／request／action 關聯與 canonical 表示。
  - 多 writer、重啟、部分寫入、重複 sequence、gap、截斷與內容異動會被偵測並明確報錯，不會當成正常空資料。
  - show／export 預設只輸出已遮罩資料，integrity 狀態可供 smoke test 斷言。
  - 形成後續 hash chain 可直接使用的穩定 substrate，且 migration 有版本標記。
- **Non-goals**
  - 不提供外部簽章服務、硬體金鑰、遠端 immutable storage 或 SIEM。
  - 不宣稱本機 user／root 無法竄改；需明列本機威脅模型。
  - 不建立 principal、authentication、grant 或 Trust Tier。
- **學習紀錄應補記什麼**
  - 控制面路徑、檔案權限、redaction 規則、誤遮罩／漏遮罩測試。
  - sequence 分配、併發、crash recovery、gap 與 tamper smoke 證據。
  - 舊 audit／session 格式的讀取、遷移或封存決策。
  - 本機完整性仍無法涵蓋的攻擊者能力。

## v0.9.5 — Principal / API Key scope 模型

- **問題 / 為何阻斷 v1.0**
  - 現行 `api_key` 只用來呼叫 LLM provider，不能代表「誰」要求 tool action，也沒有可驗證的 tool scope。
  - ROADMAP 要求唯讀與完整金鑰，但目前 read、mutate、shell、高風險操作沒有統一 principal／scope 語意。
  - 沒有 principal 就無法正確綁定 session authentication、trust grant、audit 與 revoke。
- **涉及模組**
  - `src/council_agent/types.py`
  - `SecurityContext` 與 dispatcher
  - `src/council_agent/orchestrator.py`
  - `src/council_agent/llm/openrouter.py`
  - CLI／設定載入的 credential boundary
  - security、tools、orchestration specs 與 scope matrix 測試
- **驗收條件**
  - principal 有穩定 ID、種類、issuer／來源與明確 scopes；scope 至少區分 read、filesystem mutate、test、shell 與高風險管理操作。
  - provider API key 與 Council 授權憑證在型別、載入、記錄與錯誤訊息上分離，不把 provider key 當 principal。
  - dispatcher 在任何 action 前先驗證 principal 與 scope；缺失、未知或 scope 不足時 fail-closed。
  - read-only principal 無法透過 `run_tests`、複合 tool、policy、confirmation 或 wrapper 間接 mutate。
  - principal／scope decision 寫入已遮罩 audit，可追溯但不記錄原始 credential。
  - scope tightening 與 revoke 在下一次 decision 立即生效，沒有沿用過期 context。
- **Non-goals**
  - 不實作登入流程、session step-up、user-owned trust grant 或 Trust Tier。
  - 不建立遠端 IAM／OAuth provider。
  - 不改變 OpenRouter 本身的 provider 權限模型。
- **學習紀錄應補記什麼**
  - principal 類型、scope matrix、預設 scope 與 deny precedence。
  - provider credential 和 Council credential 分離的資料流。
  - read-only 旁路測試、credential redaction 與 revoke 生效證據。
  - 暫不支援的 principal 類型。

## v0.9.6 — Session authentication foundation

- **問題 / 為何阻斷 v1.0**
  - UUID session 只能關聯紀錄，不能證明使用者已驗證。
  - Tier 2 與危險操作需要額外認證，但目前沒有 challenge、有效期、step-up、重放防護或 principal 綁定。
  - 若先做 Trust Tier 再補 authentication，`--yes` 或持有 session ID 可能被誤當成高權限證據。
- **涉及模組**
  - `src/council_agent/sandbox/session.py`
  - `src/council_agent/orchestrator.py`
  - `SecurityContext`、principal 與 dispatcher
  - CLI credential input 邊界
  - audit event schema
  - security、sandbox、orchestration specs 與認證測試
- **驗收條件**
  - authentication state 與 session ID 分離，且綁定 principal、workspace、session、用途與有效期。
  - 高權限 decision 可要求 fresh step-up；缺少、過期、錯誤 principal、錯誤 workspace 或錯誤 action 的證據均拒絕。
  - challenge／token 不可重放；passphrase 或 verifier 不以明文寫入 policy、session、audit、console 或 evidence。
  - 非 TTY 與自動化環境有明確、可撤銷的測試／服務認證方式，不以 `--yes` 取代認證。
  - authentication 成功、失敗、到期、revoke 與 replay 都有已遮罩 audit。
  - crash／restart 後的狀態恢復與失效規則明確且可測。
- **Non-goals**
  - 不實作 Trust Tier 0/1/2 決策。
  - 不提供遠端 SSO、OAuth、WebAuthn 或多使用者伺服器。
  - 不在此版建立 trust grant store。
- **學習紀錄應補記什麼**
  - authentication threat model、有效期、step-up 條件與儲存邊界。
  - replay、expiry、principal／workspace mismatch 與非 TTY 測試證據。
  - credential redaction 與復原／遺失處理。
  - 未涵蓋的本機攻擊者能力。

## v0.9.7 — User-owned trust grant store

- **問題 / 為何阻斷 v1.0**
  - Trust grant 若放在 workspace，Agent 可自行授權；若不綁 principal、action 與 scope，grant 會過度擴張。
  - ROADMAP 的 `council trust grant/revoke/list` 需要可靠的持久層、所有權、原子更新與 revoke 語意。
  - 沒有 user-owned store，就無法安全地為 v1.0-alpha 提供信任來源。
- **涉及模組**
  - `src/council_agent/security/` 下的 grant store 責任
  - `SecurityContext`、principal、session authentication 與 dispatcher
  - CLI 的 trust 管理接線
  - audit、設定與 user-owned data root
  - security、orchestration specs 與 grant lifecycle 測試
- **驗收條件**
  - grant store 位於 workspace 外的使用者擁有位置，權限與 ownership 驗證失敗時 fail-closed。
  - grant 綁定 principal、canonical action／resource、scope、建立者、建立時間、可選期限與唯一 ID。
  - grant／revoke／list 需要適當 authentication；project policy 或 Agent workspace write 無法建立、擴權或恢復 grant。
  - revoke 立即生效；過期、損毀、重複、衝突與未知 schema grant 不被採用。
  - 更新具原子性與併發保護；每次管理與使用 decision 都留下已遮罩、可關聯的 audit。
  - 備份、遷移、降版與 store 損毀復原有明確手冊與測試。
- **Non-goals**
  - 不將 grant 映射成 Trust Tier runtime 行為；留到 v1.0-alpha。
  - 不允許 repo 內共享 grant 或遠端團隊同步。
  - 不以 `ConfirmMode.AUTO` 建立持久 grant。
- **學習紀錄應補記什麼**
  - store 路徑、ownership／permission 判定、schema 與原子更新策略。
  - grant scope 範例、過度寬鬆案例、expiry／revoke／corruption 測試。
  - project policy 無法授權的旁路證據。
  - migration、backup 與使用者復原流程。

## v0.9.8 — Trust Tier decision matrix

- **問題 / 為何阻斷 v1.0**
  - `ConfirmMode` 描述「如何處理互動確認」，不是「呼叫者擁有什麼權限」。目前 `auto` 可允許需確認操作，容易被誤接成 Tier 2。
  - Trust Tier 前需要唯一、可審查的 decision matrix，明定 policy deny、scope、authentication、grant、action risk 與互動的優先序。
  - 若沒有矩陣與 reason code，CLI、dispatcher、audit、Verification 可能對同一 action 得到不同結論。
- **涉及模組**
  - `src/council_agent/security/confirm.py`
  - `SecurityContext`、dispatcher、principal、authentication 與 grant contracts
  - security、tools、orchestration specs
  - decision table／property tests 與 CLI mode tests
  - 真人與 Agent 測試手冊中的術語
- **驗收條件**
  - spec 以完整矩陣定義輸入、deny precedence、`deny`／`require_confirmation`／`allow` 輸出與穩定 reason code。
  - project policy deny、scope 不足、authentication 不足與無效 grant 永遠不能被 tier 或 `ConfirmMode` 覆蓋。
  - `ConfirmMode` 只決定 prompt／auto-response／非 TTY 行為；它不創造 principal、scope、authentication 或 grant。
  - `--yes` 的文件與測試明確顯示它不是提權旗標。
  - 同一 decision vector 在 CLI、Crew 與 library 產品入口得到相同結果與 audit reason。
  - v1.0-alpha 可直接以這份已審查矩陣接上 Tier 0/1/2，不需重寫底層安全契約。
- **Non-goals**
  - **不在 v0.9.8 啟用 Trust Tier 0/1/2 runtime 本體、`--trust-tier` 或 tier 對外 CLI。**
  - 不新增 grant 類型、遠端政策或角色階層。
  - 不把使用者點選確認永久轉為 grant。
- **學習紀錄應補記什麼**
  - 核准的矩陣版本、每個輸入維度、deny precedence 與 reason codes。
  - `ConfirmMode` 舊行為的相容／遷移決策。
  - `--yes`、非 TTY、缺少 authentication、無效 grant 的測試向量。
  - 留給 v1.0-alpha 的 tier runtime 接線清單。

## v0.9.9 — Verification/escalation evidence closure + 文件校正

- **問題 / 為何阻斷 v1.0**
  - 現行流程在 Verification FAIL 後執行 Escalation，卻不重新驗證新的 `ExecutionResult`；最終輸出與回傳 verdict 不一致。
  - Escalation 產生的新結果沒有完整 tool summaries／decision／audit evidence，無法證明修正真的通過安全與成功條件。
  - 缺少真人與 Agent 的獨立測試手冊，文件對「已完成」與「v1.0 才提供」的描述也尚未形成發行證據。
- **涉及模組**
  - `src/council_agent/orchestrator.py`
  - `src/council_agent/crews/verification.py`
  - Escalation crew 與 tool 接線
  - `src/council_agent/types.py`
  - tracker、dispatcher、audit 與 session evidence
  - `ROADMAP.md`、`README.md`、`AGENTS.md`、`LESSONS.md`
  - `docs/releases/testing/`
  - orchestration spec 與 Verification／Escalation 整合測試
- **驗收條件**
  - 每次 Escalation 後都以同一成功標準重新 Verification；仍失敗時最終狀態保持 FAIL，不得以新文字輸出掩蓋。
  - 最終 verdict、final output、tool summaries、policy／authorization decisions、test exit codes 與 audit correlation 指向同一次最終嘗試。
  - retry／escalation 上限、停止原因與每次 attempt ID 可追溯；舊 evidence 保留，不被覆寫。
  - Verification 不只相信 LLM 敘述；缺少必要 tool／test evidence 時不能判 PASS。
  - ROADMAP、main specs、README、CLI help 與 release notes 對能力、啟發式限制與 Non-goals 一致。
  - 真人與 Agent 測試手冊完成，分別由未參與實作的人與無先前脈絡的 Agent 走完，結果寫回本紀錄。
  - 完整 smoke matrix 與 `./scripts/check.sh` 在同一 release candidate commit 通過。
- **Non-goals**
  - 不實作 Trust Tier runtime 本體；它仍是 v1.0-alpha 的獨立 OpenSpec change。
  - 不用更多 LLM 自評取代結構化證據。
  - 不順帶新增與 evidence closure 無關的功能。
- **學習紀錄應補記什麼**
  - 每個 attempt 的 ID、輸入、tool／test evidence、verdict 與最終選擇。
  - Escalation 後重新 Verification 的 PASS／FAIL／上限案例。
  - 文件衝突清單的關閉證據與仍接受的 P2。
  - 真人、Agent 手冊執行者、基準 commit、結果、疑義與修正。

## v1.0-alpha 准入決策

只有下列條件全數成立時，才可提出 v1.0-alpha Trust Tier change：

- v0.9.1–v0.9.9 已依序完成並發佈。
- 所有 P0／P1 已關閉，且有拒絕、旁路、無副作用與 smoke evidence。
- OpenSpec changes 已 sync／archive，`./scripts/check.sh` 通過。
- 完整 smoke matrix 通過。
- 真人與 Agent 測試手冊已由獨立執行者完成。
- 剩餘 P2 有明確接受理由，且不影響安全正確性或文件真實性。

alpha 才開始實作 Trust Tier 0/1/2 runtime；本紀錄中的 v0.9.x 工作只建立可信基礎與決策契約。

## 後續紀錄格式

每完成盤點、OpenSpec proposal、設計決策、實作階段、驗證、archive、patch release、alpha／beta／GA gate，都在本檔追加：

```markdown
### YYYY-MM-DD HH:MM UTC — <階段／版本／change>

- 狀態：開始／通過／失敗／阻斷／接受風險
- 基準：branch、commit、package version、OpenSpec change
- 觀察：來源宣稱與實際證據
- 矛盾或風險：ID、P0／P1／P2、可重現路徑
- 決策：採用方案、替代方案與理由
- 驗證：指令、exit code、結果、`docs/releases/evidence/<version-or-stage>/` 路徑
- 剩餘風險：責任版本與停止條件
- 文件影響：ROADMAP、spec、手冊、release notes
- 下一步：唯一可執行動作
```

不得刪除舊紀錄來隱藏失敗；結論改變時新增一筆更正，並引用被更正的日期與問題 ID。

## 執行紀錄

### 2026-08-11 14:47 UTC — v1.0 準備文件初稿

- 狀態：阻斷（完整 release gate 尚未通過；文件初稿已完成）
- 基準：branch `cursor/major-release-prep-docs-a526`、commit `4a3f53c`、package v0.9.0、既有 active change `v1-prep`
- 觀察：
  - `uv run pytest`：182 passed。
  - `validate --specs --strict`：orchestration、sandbox、security、tools 共 4 個 specs 通過。
  - `validate --changes --strict`：工作開始前已存在的 `openspec/changes/v1-prep/` 只有 `.openspec.yaml`，change 不完整，因此失敗。
- 矛盾或風險：發行 gate 要求無未完成 active change；目前 `v1-prep` 尚未形成 proposal、design、spec delta 與 tasks。此為流程阻斷，不把它誤記成產品 P0／P1 已修正。
- 決策：保留既有 `v1-prep`，不在文件撰寫任務中擅自補寫、刪除或歸檔；兩份準備文件只記錄探索與 playbook。
- 驗證：
  - `./scripts/check.sh`：pytest 通過，changes strict validation 失敗，exit code 1。
  - `npx @fission-ai/openspec@latest validate --specs --strict`：4 passed，exit code 0。
  - evidence：本次 Agent 執行輸出；尚未建立 release evidence bundle。
- 剩餘風險：`v1-prep` 未完成前，不得宣稱完整 release gate 通過，也不得進 alpha。
- 文件影響：本紀錄明列阻斷；playbook 保持「tag 前不得有 active change」規則。
- 下一步：由 `v1-prep` 擁有者完成或移除該 change 後，重新執行 `./scripts/check.sh`。

### 2026-08-11 14:54 UTC — 測試文件與已知問題清單落地

- 狀態：通過
- 基準：branch `cursor/v1-prep-d691`、package v0.9.0、active change `v1-prep`
- 觀察：已建立文件入口、公開測試手冊、真人案例、機器檢查清單、issue 回報範本、v1.0-alpha 已知問題與 smoke suite。
- 決策：文件明列 shell 只驗證 `cwd`、classifier fail-open、project policy 與 audit 的現行限制；v0.9.0 預期失敗不得算 release gate 通過。
- 剩餘風險：v0.9.1–v0.9.9 尚未完成；公開 beta 前所有 P0 必須關閉。
- 下一步：完成 OpenSpec v1-prep artifacts

### 2026-08-11 15:01 UTC — OpenSpec v1-prep sync／validate／archive

- 狀態：通過
- 基準：branch `cursor/v1-prep-d691`、package v0.9.0、change `v1-prep` → `openspec/changes/archive/2026-08-11-v1-prep`
- 觀察：
  - `./scripts/check.sh`：182 passed；changes／specs strict 全綠（含新 capability `release-prep`）。
  - 文件入口 `docs/index.md`、公開測試、smoke、known-issues、playbook、learning-log 已落地。
  - ROADMAP／README／LESSONS 已校正過度宣稱並寫入 v0.9.1–v0.9.9 序列。
- 矛盾或風險：產品 P0／P1 **尚未修正**（僅盤點與閘門）；不得進 alpha。
- 決策：本 change 僅文件／流程契約；runtime 清債由後續獨立 change 依序執行。
- 驗證：`./scripts/check.sh` exit 0；evidence 為本機 CI 輸出。
- 剩餘風險：v0.9.1 shell containment 未開工前，shell 越界與 classifier fail-open 仍在。
- 文件影響：`openspec/specs/release-prep/spec.md` 成為來源真相之一。
- 下一步：開 OpenSpec change `shell-containment`（目標 release v0.9.1），依 playbook 執行。

### 2026-08-11 16:39 UTC — v0.9.1 shell-containment 實作與 regression

- 狀態：實作與自動化 regression 通過；OpenSpec sync／archive 與 release branch 版本 bump 分開執行
- 基準：branch `cursor/v091-shell-containment-d691`、runtime revision `65dcefd`、package v0.9.0、change `shell-containment`
- 原始 bypass：
  - 未知 executable 未命中 regex 時變成 `read`，再由 `shell=True` 執行。
  - classifier 判斷 raw text，shell 可再解讀 `;`、pipeline、redirect、backtick、`$()`、環境變數與多命令。
  - cwd 在 workspace 內不會阻止 `cat`／`python` 使用 absolute／traversal／symlink 路徑讀取外部 sentinel。
  - `run_tests` 以 `args.split()` 拆 token，再用空白重組 shell command，空白路徑與 quoted values 會漂移。
- 決策：
  - 以 typed accepted／rejected analysis 建立一個 immutable argv、明確 category、非空 `matched_rule` 與 path operands；沒有 unknown-to-read fallback。
  - raw input 先掃 shell control，再只做一次 `shlex.split(posix=True)`；接受後解析所有 path operands、建立 canonical policy 表示、套用 confirmation，最後把 retained argv 交給 `subprocess.run(..., shell=False)`。
  - `run_tests` 保留原本 string `args` API，但 typed `path` 是單一 argv element，args 只解析一次；test action 明確分類為 `write`。
- 明確拒絕：
  - syntax：`;`、`|`、`&`、backtick、`$`、`(`、`)`、`<`、`>`、CR／LF（即使在 quotes 內）、NUL、unbalanced quoting。
  - executable／form：未知與 path-qualified executable、`python`／`uv`／shell interpreters、未建模 command options、`mv`／`cp` target-directory forms。
  - pytest args：未知 option、`--basetemp`／`--junitxml` 等未建模 path-writing options、shell control 與 malformed quoting。
- 相容性影響：原本依賴任意 shell command、`python -c`、`uv run`、expansion、redirect、pipeline、command substitution、多命令或 raw spacing policy pattern 的 caller 會 fail-closed；pytest caller 應改用 `run_tests`。既有 classifier 測試因此更新為新 spec，而其他 regression 測試保持通過。
- refusal contract：parser／containment 失敗回傳 `ToolResult(success=False)`；`metadata.rejection_reason` 為 `unsupported`、`unparseable`、`shell_metachar`、`workspace_boundary` 或 `denied_path`，pre-execution refusal 沒有 `exit_code`。
- 驗證：
  - pure analyzer／pytest args：89 passed，exit code 0。
  - targeted shell／workspace／policy suite：95 passed，exit code 0。
  - full regression：291 passed，exit code 0。
  - synced main specs strict validation：security／tools 等 5 specs passed，exit code 0。
  - `./scripts/check.sh`：291 tests、active change 1/1、main specs 5/5，同一 revision `57f846f` exit code 0。
  - post-archive `./scripts/check.sh`：291 tests、no active changes、main specs 5/5，revision `2d55164` exit code 0。
  - `cat`／`python` outside sentinel、outside `cp`／`mv` destination、mixed operands、traversal、symlink、inherited environment 與 compound syntax全部斷言 sentinel 不變且 subprocess call count 為 0。
  - `run_tests` 真實執行含空白、Unicode、引號、`;`、`$()` 與 backtick 的目錄：1 passed，exit code 0；quoted `-k` value 保持單一 argv element。
  - 詳細 test／commit 對照見 [`v0.9.1-shell-containment-evidence.md`](v0.9.1-shell-containment-evidence.md)。
- 剩餘風險／延期責任：
  - 允許且通過現有 policy／confirmation 的 program 仍可自行存取網路、啟動 process 或解讀外部資源；沒有 OS、network、process-tree、environment／`PATH` isolation 或 TOCTOU 防護。
  - 唯一 dispatcher／`SecurityContext` 仍由 v0.9.2 擁有；policy trust boundary、audit integrity、principal、authentication、grant、decision matrix 與 evidence closure 依 v0.9.3–v0.9.9 順序處理。
  - Trust Tier 0/1/2 runtime 與 `council trust` 仍只屬 v1.0-alpha，未在本 change 實作。
- 文件影響：README、known issues、v0.9.x handoff、smoke／manual status 與本 learning log 更新；未 bump package version。
- Archive：delta 已同步，change 移至 `openspec/changes/archive/2026-08-11-shell-containment/`；tasks 28/28 complete，無 active `shell-containment` delta。
- 下一步：合併 feature PR；之後只在 `release/0.9.1` 做版本 bump／tag。

### 2026-08-11 16:58 UTC — v0.9.1 merged and tagged

- 狀態：通過
- 基準：tag `v0.9.1`、PR #8、archive `2026-08-11-shell-containment`
- 驗證：`./scripts/check.sh` 291 passed
- 下一步：開 `policy-middleware` change（v0.9.2）

### 2026-08-11 17:26 UTC — v0.9.2 Policy Middleware 實作與 regression

- 狀態：runtime／integration regression 通過；OpenSpec sync／archive 與 post-archive gate 待完成
- 基準：branch `cursor/v092-policy-middleware-d691`、pre-archive implementation revision `884e278`、package v0.9.1、change `policy-middleware`
- 原始旁路：
  - direct `tools.filesystem`／`tools.shell` 呼叫只執行 tool-local guard，沒有 wrapper-owned tracker、session、audit。
  - Execution Crew `_invoke` 自行 pre-check limit、呼叫 `tracker.record()`、append session、`record_audit_event()`；direct library 與 Crew path 不同。
  - orchestrator 分別安裝 project policy、confirmation、audit 三個 ContextVars，可能形成混用 snapshot／cleanup 漏洞。
- 唯一產品入口：
  - `tools` package 與 `tools.filesystem`／`tools.shell` 的六個 public functions 全部呼叫 `security.middleware.invoke()`。
  - Execution Crew 六個 adapters 只轉接 typed input 與格式化 `ToolResult`；不接收 tracker/session，不做 policy／limit／session／audit decision。
  - `run_council` 建立一份 `SecurityContext` 並跨 planning、execution、verification、escalation 安裝；目前 escalation 沒有 tools，但無第二個 product dispatcher。
- `SecurityContext` 決策：
  - frozen snapshot 包含 request ID、optional session ID、workspace guard、project policy、`v0.9-unversioned` label、confirmation、tracker、optional session/audit writer。
  - label 不是 policy schema version；schema version 與 trust boundary 仍屬 v0.9.3。
  - close-on-exit lease 讓 owner reset 後的 copied ContextVar 也以 `security_context_closed` 拒絕；未安裝是 `security_context_missing`。
  - session workspace、session ID 與 audit logger session ID mismatch 在 operation 前拒絕。
- Dispatcher 不變量：
  - 一個 action ID 固定串起 context validation、limit、tool-specific policy／classification／confirmation、operation、tracker、optional session、optional audit。
  - admitted action 只有一個 tracker summary／session result；`run_tests` 不遞迴 `run_command`。
  - sandbox audit 每個 action 是同 request/action/session ID 的 `attempt` + `result`；policy／confirmation／limit deny、expected failure、exception、success 都經 middleware result。
  - 無 sandbox 時仍有同一 middleware 與 in-memory tracker，但 `session=None`／`audit_logger=None`，不建立 `.council/` durable evidence。
- 旁路／一致性證據：
  - public filesystem mutation／shell 在缺 context 時不產生檔案或 process side effect。
  - direct 與 Crew 對同一 unsupported action 都產生 `decision=deny`、`rejection_reason=unsupported`。
  - 一個 Crew action 的 evidence 是一個 tracker、一個 session line、兩個 audit phases，wrapper 無重複。
  - private underscore helpers 不從 `tools.__all__` export，且 security-sensitive helper 需要 active context；它們不是支援的 product authorization API。
- 驗證：
  - middleware core phase：303 passed。
  - public boundary phase：311 passed。
  - orchestrator／Crew integrated full regression：315 passed，exit code 0。
  - change strict validation：1/1 passed，exit code 0。
  - 詳細 evidence：[`v0.9.2-policy-middleware-evidence.md`](v0.9.2-policy-middleware-evidence.md)。
- 剩餘風險／延期責任：
  - Python 同 process 的 hostile caller 仍可 introspect private objects；本版關閉支援的產品入口旁路，不宣稱 language-runtime isolation。
  - audit redaction、control-plane、sequence／gap、hash chain 屬 v0.9.4；目前 correlation 不是 integrity。
  - project policy restrict-only boundary／versioned schema 屬 v0.9.3；principal、authentication、grant、decision matrix 仍依 v0.9.5–v0.9.8。
  - Trust Tier 0/1/2 runtime 與 `council trust` 仍只屬 v1.0-alpha。
- 文件影響：README、known issues、v0.9.x handoff 與本 learning log 更新；feature branch 不 bump version。
- 下一步：完成 docs regression，sync security／tools／orchestration delta，strict validate，archive，再執行 post-archive `./scripts/check.sh`。

### 2026-08-11 17:32 UTC — v0.9.2 tagged

- 狀態：通過
- 基準：tag `v0.9.2`、PR #9
- 驗證：315 passed
- 下一步：v0.9.3 `policy-trust-boundary`
