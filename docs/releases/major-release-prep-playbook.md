# 主要版本發行準備 Playbook

> 適用範圍：Council Agent 從 v0.9.0 整理 patch 版、進入 v1.0-alpha、v1.0-beta，最後發佈 v1.0 GA 的準備工作。
>
> **重要邊界：本 playbook 不實作 Trust Tier 本體；Trust Tier 0/1/2 的正式行為屬於 v1.0-alpha。** v0.9.x 只處理進入 alpha 前必須可信的安全基礎、決策契約、證據鏈與文件。

## 1. 目標與使用原則

本 playbook 供 Agent 逐步執行。每一階段都必須：

1. 先取得可重現的現況證據，再做判斷。
2. 將發現、決策、驗證結果與剩餘風險寫入 `/workspace/docs/releases/learning-log-v1-prep.md`。
3. 有阻斷條件時停止，不得用「之後補」跳過 P0／P1。
4. 功能、修正與重構遵循 OpenSpec；一個 patch 對應一個主要問題與一個 change。
5. 所有測試產物放在 `tmp_path`、系統暫存目錄或版本化 evidence 目錄，不得污染 repo。
6. 安全能力以實際程式、測試與 smoke test 證據為準；不得只因 ROADMAP 或舊 proposal 寫了就宣稱完成。

### 問題分級

| 等級 | 判定 | 發行規則 |
|---|---|---|
| P0 | 可繞過安全邊界、未授權執行／提權、秘密外洩或審計可被無聲破壞 | 立即停止升版；不得進 alpha |
| P1 | 核心安全控制缺口、決策語意不一致、無法可靠驗證最終結果 | 排入 v0.9.x；不得進 alpha |
| P2 | 文件、可維運性、診斷性或低風險一致性問題 | alpha 前應盡量清完；未清項目須有接受理由、責任版本與證據 |

不得只依「目前沒有失敗測試」調降等級。調降必須附威脅情境、不可達證據與回歸測試。

## 2. 強制學習紀錄

### 固定路徑

- 主紀錄：`/workspace/docs/releases/learning-log-v1-prep.md`
- 驗證證據：`/workspace/docs/releases/evidence/<version-or-stage>/`
- 真人測試手冊：`/workspace/docs/releases/testing/<version>-human-test-manual.md`
- Agent 測試手冊：`/workspace/docs/releases/testing/<version>-agent-test-manual.md`

`<version-or-stage>` 使用 `v0.9.1`、`v1.0.0-alpha.1`、`v1.0.0-beta.1`、`v1.0.0` 等可追溯名稱。

### 每一步都要追加的格式

在開始下一步前，將下列區塊追加到主紀錄。不得覆寫先前結論；結論改變時新增一筆並連回舊紀錄。

```markdown
### YYYY-MM-DD HH:MM UTC — <階段／版本／change>

- 狀態：開始／通過／失敗／阻斷／接受風險
- 基準：branch、commit、package version、OpenSpec change
- 觀察：
  - <來源路徑或指令> 宣稱／要求什麼
  - 實際程式、測試或執行結果是什麼
- 矛盾或風險：P0／P1／P2；攻擊或失敗路徑
- 決策：採用方案、未採用方案與理由
- 驗證：
  - 指令／案例
  - 結果與 exit code
  - evidence 路徑
- 剩餘風險：無，或明列責任版本與停止條件
- 文件影響：需更新的 ROADMAP、spec、手冊與 release notes
- 下一步：唯一可執行動作
```

紀錄不得包含 API key、token、passphrase、原始秘密或未遮罩的敏感參數。若證據含敏感內容，只記錄遮罩後摘要與雜湊。

## 3. 階段 0：前置檢查

### 3.1 Git flow

執行並記錄：

```bash
git status --short --branch
git branch --show-current
git log --oneline --decorate -n 20
git tag --sort=-version:refname
```

檢查：

- [ ] 工作樹沒有不明變更；既有變更已辨識擁有者與用途。
- [ ] 不在 detached HEAD 上進行發行作業。
- [ ] feature change 從 `develop` 分出，並以 `--no-ff` 合併回 `develop`。
- [ ] `release/<version>` 只從 `develop` 分出。
- [ ] 版本 bump 只發生在 `release/*`，不在 `feature/*`。
- [ ] `feature/*` 不直接合併至 `main`。
- [ ] release 合併至 `main` 並打 tag 後，再以 `--no-ff` 合併回 `develop`。
- [ ] patch、alpha、beta、GA 都有唯一 commit 與 tag 對應，不重用 tag。

任一分支來源或未追蹤變更無法解釋時，停止。

### 3.2 Active OpenSpec changes

執行：

```bash
npx @fission-ai/openspec@latest status
npx @fission-ai/openspec@latest validate --changes --strict
npx @fission-ai/openspec@latest validate --specs --strict
```

檢查：

- [ ] 開發期間每個 active change 都對應明確版本與問題。
- [ ] `proposal.md` 有與 ROADMAP 對齊的 Non-goals。
- [ ] `design.md`、spec delta、`tasks.md` 已就緒才開始實作。
- [ ] `tasks.md` 依純函式／邊界／接線／框架／端對端順序執行，不跳步。
- [ ] 準備任何 release tag 前，delta 已 sync、specs 驗證通過、change 已 archive。
- [ ] 準備任何 release tag 前，`openspec/changes/` 沒有 active change。

不要執行未帶 `--changes` 或 `--specs` 的裸 `validate --strict` 並將其視為通過。

### 3.3 完整驗證

執行：

```bash
./scripts/check.sh
```

門檻：

- [ ] pytest 全部通過。
- [ ] active changes strict validation 通過。
- [ ] main specs strict validation 通過。
- [ ] exit code 為 0，完整輸出保存至當次 evidence 目錄。

任何一項失敗都停止升版；先建立或更新對應 OpenSpec change。

### 3.4 版本一致性

逐項核對：

- [ ] `pyproject.toml` 的 `[project].version` 與 `src/council_agent/__init__.py` 的 `__version__` 完全一致。
- [ ] `openspec/config.yaml` 的 Current version 與已發佈現況一致。
- [ ] `ROADMAP.md` 的「現況」、能力表與 Non-goals 符合實際程式。
- [ ] release notes、套件版本與 Git tag 指向同一發行內容。
- [ ] prerelease 的套件版本採 PEP 440；Git tag 可採對外顯示格式，但對照關係已記錄。例如套件 `1.0.0a1` 對應 tag `v1.0.0-alpha.1`。
- [ ] 若版本 bump 使 `uv.lock` 改變，變更已一併審查與提交。

## 4. 階段 1：矛盾／衝突盤點

### 4.1 固定比對順序

依序檢視：

1. `ROADMAP.md`：確認目標版本承諾、交付物與 Non-goals。
2. `openspec/specs/*/spec.md`：確認目前規範行為；這是現行行為的規格來源真相。
3. `openspec/changes/archive/`：確認歷史決策、曾明列的限制與延期項目；archive 是決策脈絡，不會自動覆蓋現行 spec。
4. `src/council_agent/`：找出實際入口、所有旁路、預設值與錯誤處理。
5. `tests/` 與實際 CLI：確認哪些承諾有正向、拒絕、繞過與副作用測試。
6. `README.md`、`AGENTS.md`、`CONTRIBUTING.md`、`LESSONS.md`：確認對使用者與 Agent 的說法沒有超出實際保證。

遇到不一致時，不得自行選擇最樂觀來源。建立衝突項目，直到 spec、程式、測試與文件重新一致。

### 4.2 衝突表

每個項目至少記錄：

| ID | 等級 | ROADMAP／spec 宣稱 | archive 限制 | 程式實況 | 可重現案例 | 責任版本 | 狀態 |
|---|---|---|---|---|---|---|---|
| V1-xxx | P0/P1/P2 | 路徑與條文 | 路徑與決策 | 入口與旁路 | 指令或測試 | v0.9.x | open/closed |

盤點時必查：

- 未辨識、混淆或組合 shell 指令是否 fail-open。
- `run_tests` 是否因字串拼接、空白、引號或 shell metacharacter 改變語意。
- 所有 tool 入口是否都經同一政策、授權、審計與追蹤路徑。
- 專案內可修改的檔案是否能提高信任或權限。
- 政策 schema 是否有版本，未知／未支援欄位是否 fail-fast。
- `.council/` 控制面、audit 與 trust 資料是否可被受控 Agent 改寫。
- audit 是否遮罩秘密、可排序、可偵測缺漏與竄改。
- principal、API key scope、session authentication 與 grant 的擁有者是否明確。
- `ConfirmMode` 是否被誤當成授權或 Trust Tier。
- Escalation 後的最終輸出是否重新 Verification，且 verdict 對應真正交付內容。
- 文件是否明確區分「已具備」、「啟發式」與「尚未實作」。

完成後，將新增、關閉與重新分級項目寫入主學習紀錄。

## 5. 階段 2：規劃 v0.9.x patch

### 5.1 「一版一主要問題」規則

v0.9.x 強制一個 patch 只解一個主要問題：

- 一個版本、一個 OpenSpec change、一個主要安全不變量。
- 測試、spec、必要文件可隨同該問題更新，但不得順帶實作下一版能力。
- 發現跨版相依時，前一版只建立後續可依賴的明確契約；後續行為留在既定版本。
- patch 中出現 Trust Tier 0/1/2 對外生效、`--trust-tier` 或以 tier 自動授權時，立即停止並移回 v1.0-alpha change。
- 緊急 P0 可新增 patch，但不得把兩個獨立 P0 塞進同一版；須更新序列與相依關係。

固定序列：

| 版本 | 唯一主要問題 |
|---|---|
| v0.9.1 | Shell containment（classifier fail-open、`run_tests` quoting） |
| v0.9.2 | 唯一 Policy Middleware／dispatcher + `SecurityContext` |
| v0.9.3 | 政策 trust boundary + versioned schema fail-fast |
| v0.9.4 | Audit integrity substrate（控制面保護、redaction、sequence） |
| v0.9.5 | Principal／API Key scope 模型 |
| v0.9.6 | Session authentication foundation |
| v0.9.7 | User-owned trust grant store |
| v0.9.8 | Trust Tier decision matrix（與 `ConfirmMode` 分離） |
| v0.9.9 | Verification／escalation evidence closure + 文件校正 |

詳細問題與驗收條件見 `learning-log-v1-prep.md`。

### 5.2 每個 patch 的執行循環

1. **鎖定問題**：從衝突表選一個版本項目，補上攻擊／失敗案例、Non-goals 與相依版本。
2. **建立 OpenSpec change**：proposal → design + spec delta → tasks；proposal 必須列 Non-goals。
3. **依 tasks 漸進整合**：每一階段完成後執行 `uv run pytest`，通過才進下一階段。
4. **封閉驗收條件**：新增正向、拒絕、旁路、併發／重放（適用時）與無副作用測試。
5. **完整驗證**：執行 `./scripts/check.sh`。
6. **同步與歸檔**：sync delta，驗證 specs，再 archive；確認沒有該 change 的 active 殘留。
7. **release 分支**：從 `develop` 建立 `release/0.9.x`，只在此處 bump 版本並更新現況文件。
8. **patch smoke test**：在乾淨暫存 workspace 執行本版案例與既有核心案例。
9. **發行與回合併**：release 合併至 `main`、建立不可變 tag，再 `--no-ff` 合併回 `develop`。
10. **補記學習**：寫下實際修正的不變量、未處理項目、測試證據、release commit／tag 與下一版准入條件。

任何循環缺少學習紀錄、OpenSpec 歸檔、完整驗證或 smoke evidence，該 patch 視為未完成。

## 6. Smoke test 門檻

### 6.1 執行環境與證據

- 使用乾淨安裝與新的暫存 workspace；不得依賴開發者既有 `.council/`。
- 正向與拒絕案例都要記錄 exit code、結構化結果、預期副作用與實際副作用。
- 每次執行結果保存到 `docs/releases/evidence/<version-or-stage>/smoke-test.md`；必要原始輸出放同目錄並先遮罩。
- patch 執行與該問題直接相關的子集；alpha、beta、GA 必須執行完整矩陣。

### 6.2 最低 smoke 矩陣

- [ ] 套件可安裝，`council --help` 與版本資訊可取得。
- [ ] `council sandbox init/status` 在乾淨 workspace 可重複執行。
- [ ] 無政策檔、合法政策檔、錯誤 schema、未知版本與未支援欄位行為符合規格。
- [ ] 工作區內 read／write 正向案例成功；路徑穿越、symlink escape、敏感路徑與控制面寫入被拒絕且無副作用。
- [ ] 未辨識、混淆、組合、redirect、pipeline、substitution 與危險 shell 案例 fail-closed。
- [ ] `run_tests` 可處理含空白與特殊字元的合法路徑／參數，且無 shell 注入或語意漂移。
- [ ] CLI、Crew wrapper、library／dispatcher 等產品入口無法繞過政策、授權、追蹤與審計。
- [ ] audit 會遮罩秘密、sequence 可驗證、遺失／竄改可被偵測，且 Agent 無法改寫控制面。
- [ ] read-only principal／API key scope 無法 mutate、shell 或取得更高權限。
- [ ] session authentication 的成功、失敗、到期、重放與 principal 綁定符合規格。
- [ ] trust grant 只能由使用者擁有的儲存區授予，revoke 立即生效，專案檔無法自行取得信任。
- [ ] Trust Tier 決策測試向量與 `ConfirmMode` 正交；`auto` 只控制互動，不會創造權限。
- [ ] Verification 使用真實 tool evidence；Escalation 後重新驗證，最終 verdict 對應最終輸出。
- [ ] 非 TTY、缺少 context、缺少 principal、缺少 authentication 或 context 解析失敗時 fail-closed。
- [ ] `./scripts/check.sh` 同一 commit 上通過。

### 6.3 通過標準

- 必跑案例 100% 通過，沒有「重跑就過」的 flaky 結果。
- 拒絕案例的受保護資源與外部 sentinel 完全未改變。
- 沒有未解 P0／P1。
- audit、session、console 與 evidence 不含未遮罩秘密。
- 測試結果可由另一個 Agent 依手冊重現。

任一條不符合即 smoke gate 失敗，不得升版。

## 7. 文件就緒條件

### 7.1 真人測試手冊

路徑：`docs/releases/testing/<version>-human-test-manual.md`

至少包含：

- 支援環境、安裝、升級、降版與設定備份。
- 安全模型、信任邊界、威脅模型與明確 Non-goals。
- 政策 schema 版本、遷移方式、錯誤排除與 fail-closed 行為。
- principal、API key scope、session authentication、grant、Trust Tier 與確認提示的差異。
- audit 驗證、秘密遮罩、完整性告警與復原步驟。
- 每個案例的前置條件、操作、預期畫面／結果、副作用與清理方式。
- 緊急 revoke、認證遺失、audit 損毀與政策載入失敗的處置。

### 7.2 Agent 測試手冊

路徑：`docs/releases/testing/<version>-agent-test-manual.md`

至少包含：

- 不依賴對話脈絡的完整前置條件與固定順序。
- 可直接執行的命令、fixture 建立方式、預期 exit code 與結構化斷言。
- 每個拒絕案例的「不得產生副作用」檢查。
- evidence 儲存路徑、遮罩規則、成功／失敗判定與停止條件。
- 禁止讀取、列印或提交真實秘密；認證案例使用一次性測試憑證。
- 清理只限測試 workspace，不得對 repo 或共享環境做破壞性操作。

### 7.3 文件驗收

- [ ] 一位未參與實作的人依真人手冊完成測試。
- [ ] 一個沒有先前對話脈絡的 Agent 依 Agent 手冊完成測試。
- [ ] 兩者的結果、疑義與文件修正都寫入主學習紀錄。
- [ ] README、ROADMAP、main specs、CLI help、範例政策與 release notes 使用相同術語。
- [ ] 所有尚未提供的能力明列為 Non-goal，沒有「完整安全」等超額宣稱。

## 8. 階段 3：v1.0-alpha

### 准入條件

- [ ] v0.9.1 至 v0.9.9 依序完成、發佈並回合併至 `develop`。
- [ ] 衝突表中所有 P0／P1 已解決，有程式、測試與 smoke evidence；不得只標記 accepted。
- [ ] P2 已解決，或有明確接受理由、責任版本與不影響安全正確性的證據。
- [ ] 沒有 active OpenSpec change，`./scripts/check.sh` 通過。
- [ ] 完整 smoke 矩陣通過。
- [ ] 真人與 Agent 測試手冊已由獨立執行者走完。
- [ ] v1.0-alpha 的安全模型、政策 schema、遷移與 rollback 已審閱。

准入後才建立 v1.0-alpha 的 OpenSpec change，實作 Trust Tier 0/1/2、對外 CLI 與完整授權行為。

> **再次強調：本 playbook 只定義 alpha 准入與發行閘門，不實作 Trust Tier 本體。Trust Tier 本體是 v1.0-alpha 的獨立 change。**

alpha 可變更 prerelease API，但每次變更都要提供 migration note、更新兩份測試手冊並重跑完整 smoke。

## 9. 階段 4：v1.0-beta

只有在以下條件全數成立時，才由 alpha 推進 beta：

- [ ] Trust Tier alpha change 已完成、sync、驗證與 archive。
- [ ] Tier 決策、principal scope、grant、session authentication 與 audit event schema 已凍結。
- [ ] 至少一次 alpha 全矩陣回歸沒有 P0／P1。
- [ ] 升級、降版、舊政策遷移、grant revoke 與 audit 驗證 smoke 全過。
- [ ] 最終輸出 evidence closure 可重現，沒有舊 verdict 對新輸出的情況。
- [ ] 真人與 Agent 手冊已針對 beta 重跑並修正。

beta 只接受阻斷修正、相容性修正、測試與文件校正；新安全語意回到下一個 alpha，不得暗中加入 beta。

## 10. 階段 5：v1.0 GA

### GA 准入

- [ ] beta 期間沒有未解 P0／P1；所有影響發行正確性的 P2 已關閉。
- [ ] 所有 OpenSpec change 已 archive，`openspec/changes/` 無 active change。
- [ ] `./scripts/check.sh`、完整 smoke、安裝／升級／降版、真人手冊、Agent 手冊全部通過。
- [ ] ROADMAP v1.0 Definition of Done 每一項都有 spec、測試與 evidence 對照。
- [ ] 安全限制與 Non-goals 在 README、手冊、release notes 一致。
- [ ] 版本、tag、lockfile、OpenSpec config 與 ROADMAP 現況一致。
- [ ] rollback 步驟已實測，且不會遺失或破壞 audit／grant 資料。

### GA Git flow

1. 從 `develop` 建立 `release/1.0.0`。
2. 在 release branch 更新 `pyproject.toml`、`src/council_agent/__init__.py`、`openspec/config.yaml`、ROADMAP 與 release notes。
3. 在同一 commit 執行完整驗證與 GA smoke，保存 evidence。
4. 合併至 `main`，建立 `v1.0.0` tag。
5. 將 release branch 以 `--no-ff` 合併回 `develop`。
6. 在主學習紀錄補上 commit、tag、驗證證據、已知限制與 rollback 入口。

## 11. 停止與回退條件

遇到下列任一情況立即停止升版：

- 新增或重開 P0／P1。
- security context、principal、authentication 或政策解析缺失時仍可執行。
- 任一產品入口可繞過 dispatcher／middleware。
- smoke 拒絕案例產生副作用。
- audit 或測試 evidence 出現秘密。
- Escalation 後未重新 Verification。
- active OpenSpec change 尚未歸檔。
- `./scripts/check.sh` 非 0。
- 版本或 Git flow 不一致。

回退時不得刪除失敗證據。保留原紀錄，新增一筆「失敗／回退」學習紀錄，標明最後可信 tag、受影響資料格式、復原驗證與重新進場條件。

