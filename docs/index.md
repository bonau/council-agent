# Council Agent 文件入口

> 狀態：**已發佈基線 v1.0.0-beta.3**。無新安全語意；修復自 v0.9.8 起 GitHub Actions CLI help 斷言失敗。獨立真人 TTY 仍 NOT-RUN；GA 前尚需 audit hash chain。

## 開發歷程簡報

- [Council Agent 開發歷程（PDF）](council-agent-development-journey.pdf) — 從 v0.1.0 到 v1.0.0-beta.2 的 16:9 簡報（隨 beta.3 入庫）

## 目前基線

- 套件版本：`1.0.0b3`／tag 目標 `v1.0.0-beta.3`。
- Trust Tier 0／1／2 runtime 與 matrix-v2 已在 v1.0.0-alpha.1 啟用；beta 凍結該語意。
- Agent 公開測試矩陣（含 LIVE-01）已 PASS（ACCEPTED GATE A）；獨立真人 TTY 仍待後續 beta。
- 公開 beta 門檻：所有 P0 必須關閉；若仍有 P0，不得邀請外部測試者。
- 未知／複合 shell fail-closed，argv + `shell=False`；受支援 command 的 path operands 經 `WorkspaceGuard`。Mandatory dispatcher、principal／auth／grant-store、Trust Tier 與 attempt-scoped Verification 已接線。這仍**不是真正的 OS sandbox**。
- `ConfirmMode` 不等於 Trust Tier；`--yes` 只跳過互動確認，**不等於完整授權或提權**。

## 測試文件

- [`testing/v1.0-beta-public-testing.md`](testing/v1.0-beta-public-testing.md) — 公開 beta 測試者手冊、安全警告與停止條件。
- [`testing/manual-test-cases.md`](testing/manual-test-cases.md) — 真人 Smoke／Manual 案例與證據要求。
- [`testing/agent-checklist.yaml`](testing/agent-checklist.yaml) — Agent 可讀的結構化檢查清單。
- [`testing/smoke-suite.md`](testing/smoke-suite.md) — SMK-00～SMK-08 與 LIVE-01 的 smoke suite 設計。
- [`testing/issue-report-template.md`](testing/issue-report-template.md) — 測試問題回報範本。

## 發行準備文件

- [`releases/major-release-prep-playbook.md`](releases/major-release-prep-playbook.md) — v0.9.x、v1.0-alpha、beta 與 GA 發行閘門。
- [`releases/learning-log-v1-prep.md`](releases/learning-log-v1-prep.md) — 探索發現、決策與驗證紀錄。
- [`releases/v1.0-alpha-known-issues.md`](releases/v1.0-alpha-known-issues.md) — v1.0-alpha 前 P0／P1／P2 已知問題。
- [`releases/v0.9.9-evidence-closure-evidence.md`](releases/v0.9.9-evidence-closure-evidence.md) — V1-010／SEC-P1-002、V1-011 的 attempt closure、文件校正與 regression 證據。

## 使用原則

1. 只在一次性、無真實秘密、可丟棄的 workspace 執行測試。
2. 以程式、測試、審計與副作用證據判定結果，不以文件宣稱代替驗證。
3. 現行 classifier 對未知／不支援指令 fail-closed；project policy 是 restrict-only workspace input；audit 有 redaction／sequence／per-event integrity；所有 product tools 經 mandatory dispatcher；Trust Tier 0／1／2 已接線。但 host／external／project tests 不受 OS containment，audit 無 predecessor hash chain 或外部錨點。不得宣稱具完整安全框架。
4. 測試發現 P0 時立即停止公開測試，保存遮罩後證據並依回報範本通報。
