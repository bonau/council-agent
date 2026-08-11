# 測試問題回報範本

> 疑似 P0、越界執行、未授權操作或秘密外洩時，**不要建立公開 issue**。先停止測試、撤銷一次性憑證，透過維護者指定的私人安全通報管道回報。

## 標題

`[測試][P?][案例 ID] 一句話描述可觀察結果`

## 基本資料

- 案例 ID：`SMK-__`／`MAN-__`／`LIVE-01`
- 初判等級：P0／P1／P2／待分級
- 結果：FAIL／BLOCKED
- 首次發現時間：`YYYY-MM-DD HH:MM UTC`
- 測試者：
- 是否已停止測試：是／否
- 是否需要私人通報：是／否

## 發行基線

- Council Agent 版本：
- Git commit：
- 安裝來源與 artifact SHA-256：
- Python 版本：
- OS／架構：
- 一次性環境類型：VM／容器／其他
- workspace realpath：
- project policy SHA-256：
- OpenSpec change／release candidate：

## 安全邊界確認

- [ ] 測試在一次性、非特權環境執行。
- [ ] 未使用正式資料或真實長效憑證。
- [ ] 已知 shell 是受限 simple-command／argv／path-operand boundary，但仍不是真 OS sandbox；`run_tests` project code 不受 OS containment。
- [ ] 未把 `ConfirmMode` 當成 Trust Tier，也未把 `--yes` 當成完整授權。
- [ ] 已檢查 classifier 對未知／混淆／複合形式 fail-closed，且未把拒絕當 PASS。
- [ ] 已考慮 project policy 僅能縮權；product tools 禁止直接改 policy，但 host／external／test process 不在此邊界。
- [ ] 已知 audit 有 redaction、sequence、canonical event ID 與 exact correlation，但無 predecessor-linked／external anchor。
- [ ] 已知 grant store foundation 尚未接產品 tool，Trust Tier 0/1/2 runtime 尚未實作。

## 問題摘要

用三至五句描述：

1. 測試者執行什麼。
2. 預期安全或功能不變量是什麼。
3. 實際發生什麼。
4. 是否有檔案、程序、網路、政策、審計或憑證副作用。

## 最小重現步驟

> 只放無害、已遮罩、可在一次性環境執行的步驟。P0 exploit 細節只透過私人管道提供。

1. 
2. 
3. 

```text
已遮罩的命令或輸入
```

## 預期結果

- 預期 exit code：
- 預期 decision／reason：
- 預期 confirmation：
- 預期 audit event：
- 預期檔案／程序／網路副作用：
- 預期外部 sentinel SHA-256：

## 實際結果

- 實際 exit code：
- 實際 decision／reason：
- 實際 confirmation：
- 實際 audit event：
- 實際副作用：
- 外部 sentinel SHA-256（前／後）：

```text
已遮罩的 stdout／stderr 摘要
```

## 證據

- Evidence 路徑或私人附件：
- Workspace diff：
- Pipeline attempt／request／action／session correlation ID：
- Audit event 範圍：
- 螢幕截圖或錄影：
- 可重現次數：`N/N`
- 是否 flaky：是／否／未知

### 遮罩檢查

- [ ] 不含 API key、token、passphrase、cookie、SSH key 或 Authorization header。
- [ ] 不含真實使用者、客戶資料或未公開原始碼。
- [ ] 絕對路徑、帳號與主機名稱已按需要匿名化。
- [ ] 使用的是明確標示為假的 marker，不是真實秘密。

## 影響與分級理由

- 受影響入口：CLI／Crew wrapper／library／filesystem／shell／audit／policy／其他
- 可否繞過 policy／confirmation／workspace boundary：
- 可否造成未授權讀寫、提權、秘密外洩或審計無聲破壞：
- P0／P1／P2 理由：
- 對公開 beta 的影響：阻斷／不阻斷／待決定

## 暫時處置

- [ ] 已停止後續案例。
- [ ] 已撤銷一次性 credential。
- [ ] 已保存遮罩後證據。
- [ ] 已確認 outside sentinel 與其他受保護資源。
- [ ] 已隔離或丟棄測試環境。

## 建議驗收條件

- [ ] 新增最小正向與拒絕回歸測試。
- [ ] 新增旁路與無副作用測試。
- [ ] 在乾淨一次性 workspace 重跑原案例。
- [ ] `./scripts/check.sh` 通過。
- [ ] 對應 OpenSpec delta、文件與已知問題已更新。
- [ ] 若為 P0，關閉證據已由獨立測試者重現。

## 相關連結

- 已知問題 ID：
- OpenSpec change：
- 測試手冊案例：
- 修正 commit／PR：
- 遮罩後 evidence：
