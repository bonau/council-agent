## 1. 盤點與學習紀錄基線

- [x] 1.1 以 subagent 交叉審視 ROADMAP、openspec specs／archive、security／tools／sandbox／orchestrator 與 README 宣稱
- [x] 1.2 產出 P0／P1／P2 矛盾清單與建議 v0.9.1–v0.9.9 序列
- [x] 1.3 建立 `docs/releases/learning-log-v1-prep.md` 並寫入探索結論
- [x] 1.4 建立 `docs/releases/major-release-prep-playbook.md`（含 alpha／beta／GA 閘門與學習紀錄格式）

## 2. 已知問題與 ROADMAP 契約

- [x] 2.1 撰寫 `docs/releases/v1.0-alpha-known-issues.md`
- [x] 2.2 更新 `ROADMAP.md`：v0.9.x 清債表、alpha／beta 准入、開發順序、現況表 shell 限制說明
- [x] 2.3 校正 `README.md` 安全宣稱（filesystem vs shell、ConfirmMode、`--yes`、fail-open classifier）
- [x] 2.4 更新 `LESSONS.md` 主要版本發行準備章節

## 3. 公開測試與 Smoke 文件

- [x] 3.1 建立 `docs/index.md` 文件入口
- [x] 3.2 撰寫 `docs/testing/v1.0-beta-public-testing.md`
- [x] 3.3 撰寫 `docs/testing/manual-test-cases.md`（≥10 案例）
- [x] 3.4 撰寫 `docs/testing/agent-checklist.yaml`（≥12 cases）
- [x] 3.5 撰寫 `docs/testing/smoke-suite.md`（SMK-00～SMK-08、LIVE-01；標示預期失敗項）
- [x] 3.6 撰寫 `docs/testing/issue-report-template.md`

## 4. OpenSpec artifacts 與驗證

- [x] 4.1 完成 `proposal.md`（含 Non-goals）
- [x] 4.2 完成 `design.md` 與 `specs/release-prep/spec.md`
- [x] 4.3 將 `release-prep` delta sync 至 `openspec/specs/release-prep/spec.md`（含 Purpose）
- [x] 4.4 執行 `./scripts/check.sh` 全綠
- [x] 4.5 追加學習紀錄：驗證結果、剩餘風險、下一步（開 v0.9.1 `shell-containment` change）
- [x] 4.6 Archive `v1-prep` change（僅在 sync + validate --specs 通過後）

## 5. Verification

- [x] 5.1 `uv run pytest`
- [x] 5.2 `npx @fission-ai/openspec@latest validate --changes --strict`
- [x] 5.3 `npx @fission-ai/openspec@latest validate --specs --strict`
