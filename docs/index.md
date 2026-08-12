# Council Agent 文件入口

> 狀態：**v0.9.9 feature candidate 文件就緒／v1.0-alpha 前停止**。已發佈 package 基線是 **v0.9.8**；feature branch 不做 v0.9.9 bump/tag，也不代表 v1.0 安全能力或 alpha admission 已完成。

## 開發歷程簡報

- [Council Agent 開發歷程（PDF）](council-agent-development-journey.pdf) — 從 v0.1.0 到 v1.0.0-beta.2 的 16:9 簡報

## 目前基線

- 套件版本：v0.9.8；v0.9.9 `evidence-closure` implementation candidate。
- v0.9.1–v0.9.9 implementation 清債序列已完成；本序列停止。下一功能動作只能另開 v1.0-alpha Trust Tier change。
- v1.0-alpha admission 仍要求 v0.9.9 release/tag、零 active patch change、固定 candidate 的完整 smoke，以及獨立真人／無前置脈絡 Agent 走完手冊。
- 公開 beta 門檻：所有 P0 必須關閉；若仍有 P0，不得邀請外部測試者。
- Current candidate 已讓未知／複合 shell fail-closed，並以 argv + `shell=False` 執行；受支援 command 的 path operands 經 `WorkspaceGuard`。Mandatory dispatcher、principal/auth/grant-store foundation/matrix evidence 與 attempt-scoped Verification 已接線。這仍**不是真正的 OS sandbox**。
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
3. 現行 classifier 對未知／不支援指令 fail-closed；project policy 是受 product path deny 保護的 restrict-only workspace input，audit 有 redaction/sequence/per-event integrity，且所有 product tools 經 mandatory dispatcher。但 host／external／project tests 不受 OS containment，audit 無 external anchor，persisted grant 未接 product tools，也沒有 Trust Tier runtime。不得宣稱具完整安全框架。
4. 測試發現 P0 時立即停止公開測試，保存遮罩後證據並依回報範本通報。
