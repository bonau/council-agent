## Why

v0.9.0 已具備 classifier、確認、審計與專案政策，但探索顯示多項安全邊界與 v1.0 Trust Tier／Policy Middleware 目標衝突（shell 非真 sandbox、無唯一 middleware、classifier fail-open、政策可自我提權等）。若不先以 v0.9.x 逐一清債，v1.0-alpha 會建立在不可信基礎上。本 change 建立 v1.0 發行準備產物：矛盾盤點、子版本序列、學習紀錄、smoke／公開測試文件與 ROADMAP 更新——**不實作 Trust Tier 本體**。

## What Changes

- 新增 `docs/releases/` 主要版本發行準備 playbook 與學習紀錄
- 新增 `docs/testing/`：v1.0-beta 公開測試手冊、真人案例、Agent checklist、smoke suite、Issue 模板
- 新增 `docs/releases/v1.0-alpha-known-issues.md`（P0／P1／P2）
- 更新 `ROADMAP.md`：v0.9.1–v0.9.9 清債序列、v1.0-alpha／beta 准入條件
- 更新 `LESSONS.md`：主要版本發行準備經驗
- 釐清文件宣稱：filesystem vs shell 邊界、ConfirmMode ≠ Trust Tier

## Non-goals

- **不**實作 Trust Tier 0/1/2、`council trust`、Policy Middleware runtime、API Key 分級、Session 認證、audit hash chain（屬 v1.0-alpha／各 v0.9.x change）
- **不**在本 change 修改 `src/council_agent/` 安全行為或 bump 套件版號
- **不**關閉個別 P0（僅盤點與規劃責任版本）
- **不**開放公開 beta 或宣稱完整安全機制

## Capabilities

### New Capabilities

- `release-prep`: 主要版本發行前的準備契約——矛盾盤點、v0.9.x 一版一問題、學習紀錄、smoke／公開測試文件就緒條件、alpha／beta 准入閘門

### Modified Capabilities

- （無行為規格變更；本 change 以文件與發行流程契約為主。runtime 行為修正由後續 `shell-containment`、`policy-middleware` 等獨立 change 提出。）

## Impact

- 文件：`docs/**`、`ROADMAP.md`、`LESSONS.md`、`README.md`（安全宣稱校正）
- 流程：後續 Agent 依 playbook 自動準備 v0.9.x → alpha → beta → GA
- 程式：無直接 runtime 影響
- 驗證：`./scripts/check.sh`；OpenSpec changes／specs strict validate
