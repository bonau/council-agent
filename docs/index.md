# Council Agent 文件入口

> 狀態：**草稿／v1.0 準備階段**。本區文件以已發佈的 **v0.9.0** 為基線，描述公開測試與主要版本準備，不代表 v1.0 安全能力已完成。

## 目前基線

- 套件版本：v0.9.0。
- v1.0-alpha 前置條件：必須依序完成 v0.9.1–v0.9.9，關閉所有 P0／P1，並留下可重現證據。
- 公開 beta 門檻：所有 P0 必須關閉；若仍有 P0，不得邀請外部測試者。
- v0.9.1 implementation 已讓未知／複合 shell fail-closed，並以 argv + `shell=False` 執行；受支援 command 的 path operands 經 `WorkspaceGuard`。這仍**不是真正的 OS sandbox**。
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
- [`releases/v0.9.1-shell-containment-evidence.md`](releases/v0.9.1-shell-containment-evidence.md) — V1-001／V1-002 的正向、拒絕、旁路、sentinel 與 regression 證據。

## 使用原則

1. 只在一次性、無真實秘密、可丟棄的 workspace 執行測試。
2. 以程式、測試、審計與副作用證據判定結果，不以文件宣稱代替驗證。
3. 現行 classifier 對未知／不支援指令 fail-closed，但 project policy 仍位於 Agent 可修改的 workspace，audit 尚無 hash chain 與 secret redaction，也沒有統一 dispatcher／Trust Tier。這些限制解除前，不得宣稱具完整安全框架。
4. 測試發現 P0 時立即停止公開測試，保存遮罩後證據並依回報範本通報。
