# v1.0.0-beta.1 — Agent checklist / 真人手冊代跑（ACCEPTED GATE）

- 狀態：**通過（離線矩陣 + LIVE-01）**
- 執行者：Cloud Agent（使用者 2026-08-12 核准代跑；證據定性 **A＝Agent／ACCEPTED GATE**）
- **未宣稱**：本文件**不**偽稱獨立真人已覆核 TTY ASK UX；真人 TTY 留待下一個 beta 版本。
- 基準：
  - tag：`v1.0.0-beta.1`（`33880a55ae2d9841c021309902a1d7d91150ef74`）
  - evidence branch commit：見 git（package 仍為 `1.0.0b1`；tag→HEAD 無 `src/`／`tests/` 行為變更）
  - package：`1.0.0b1`
  - OS：`Linux 6.12.94+ x86_64`
  - Python：`3.12.3`
- 時間：離線 2026-08-12 00:03–00:07 UTC；LIVE-01 重跑 2026-08-12 03:06–03:14 UTC

## 執行項目

1. `./scripts/check.sh` → **577 passed**；OpenSpec specs 5/5；active changes 無（見 `agent-manual-check.sh.log`）。
2. 一次性暫存 workspace 跑 SMK-00～SMK-09 → **全部 PASS**；outside sentinel SHA-256 不變（見 `smoke-results.json`）。
3. Tier 向量（Tier0 refuse／auto、Tier1 write、Tier1 grant suite、Tier2 無 verifier CLI fail-closed、`--yes` 不提權、shell unsupported／metachar）→ **全部 PASS**。
4. MAN-01～MAN-14 依 `manual-test-cases.md` 對應 pytest 代跑 → **全部 PASS**（非 TTY 真人互動）。
5. LIVE-01（使用者核准 + 環境內 `OPENROUTER_API_KEY`）→ **PASS**（重跑）：
   - 前次：`401 User not found`；key 指紋 `46345f25ad7d`。
   - 本次：key 指紋 `175b4dbbf3b4`；最小 chat completions 探測 **PASS**（HTTP 200）。
   - `glm-stack` 兩次嘗試因 `deepseek/deepseek-v4-flash` 上游 Fireworks shared-pool **429** 失敗（非 auth）。
   - 改以 disposable `live01-fallback`（未 commit）：planning `z-ai/glm-5.2`、execution `openai/gpt-4o-mini`、verification／escalation `openai/gpt-5.6-luna`；`--trust-tier 1`；未使用 `--yes`。
   - Verdict **PASS**；audit 僅 `read_file`；console／session／audit **未**寫入 raw key；sentinel 不變（見 `live-01.json`、`live-01-console.redacted.txt`）。

## 判定

| 區塊 | 結果 |
|------|------|
| SMK-00～SMK-09 | PASS |
| Tier 向量 | PASS |
| MAN-01～MAN-14（Agent proxy） | PASS |
| LIVE-01 | PASS（fallback preset；見上） |
| 獨立真人 TTY ASK | NOT-RUN（約定留待下一 beta） |

## 後續

- 下一 beta：補獨立真人 TTY（MAN-05／SMK-05 ASK 選是／否等）。
- 若需以預設 `glm-stack`（含 deepseek）再驗證 LIVE，須等上游 rate limit／BYOK 解除後重跑。
