# v1.0.0-beta.1 — Smoke / Agent re-run（公開測試代跑）

- 狀態：離線矩陣**通過**；LIVE-01 **FAIL**（provider 401）
- 執行者：Cloud Agent（使用者核准 ACCEPTED GATE A）
- 時間：2026-08-12 00:03–00:07 UTC
- 基準：
  - tag：`v1.0.0-beta.1`（`33880a55ae2d9841c021309902a1d7d91150ef74`）
  - package：`1.0.0b1`
  - OS：`Linux 6.12.94+ x86_64`
  - Python：`3.12.3`
- Workspace：一次性 `$COUNCIL_TEST_ROOT`；outside sentinel 前後 SHA-256 相同
- 真人手冊：ACCEPTED GATE（見 `human-manual-status.md`）；TTY 留待下一 beta

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
| LIVE-01 | FAIL（OpenRouter chat 401 User not found；無 secret 落盤；sentinel 不變） |

結構化輸出：`smoke-results.json`、`live-01.json`。`./scripts/check.sh`：577 passed；specs 5/5；no active changes（見 `agent-manual-check.sh.log`）。

Tier／grant／shell 向量另見 `smoke-results.json` → `tier_cases`（全部 PASS；含 CLI Tier 2 無 `COUNCIL_AUTH_SECRET` fail-closed）。
