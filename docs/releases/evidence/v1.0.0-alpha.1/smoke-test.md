# v1.0.0-alpha.1 admission — Smoke matrix

- 狀態：通過（離線 SMK-00～SMK-09）
- 執行者：Cloud Agent（代跑 admission；使用者核准選項 1）
- 時間：2026-08-11 22:59–23:05 UTC
- 基準：
  - branch：`cursor/v1-admission-fce3`
  - commit：`4f41a8753897b295142e62ddfd6d4a6e1017493e`
  - package：`0.9.9`
  - OS：`Linux 6.12.94+ x86_64`
  - Python：`3.12.3`
- Workspace：`$COUNCIL_TEST_ROOT` 一次性暫存；outside sentinel 前後 SHA-256 相同
- LIVE-01：BLOCKED（無核准之 provider credential／外連）

## 結果

| ID | 結果 |
|----|------|
| SMK-00 | PASS |
| SMK-01 | PASS |
| SMK-02 | PASS |
| SMK-03 | PASS |
| SMK-04 | PASS |
| SMK-05 | PASS |
| SMK-06 | PASS |
| SMK-07 | PASS |
| SMK-08 | PASS |
| SMK-09 | PASS |
| LIVE-01 | BLOCKED |

結構化輸出：`smoke-results.json`。`./scripts/check.sh`：568 passed；specs 5/5；no active changes（見 `check.sh.log`）。
