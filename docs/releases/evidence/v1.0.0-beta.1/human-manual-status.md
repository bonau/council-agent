# v1.0.0-beta.1 — Human manual status

- 狀態：**ACCEPTED GATE（Agent 代跑；非獨立真人）**
- 決策依據：使用者於 2026-08-12 明確核准：
  - 代跑：是
  - 基線：`v1.0.0-beta.1`
  - 證據定性：**A（Agent／ACCEPTED GATE）**
  - **B（獨立真人 TTY）留待下一個 beta 版本**
  - LIVE-01：要跑（環境已提供 `OPENROUTER_API_KEY`）
  - 證據寫入 repo：是
- 未宣稱：本文件**不**偽稱「一位未參與實作的人」已走完 `docs/testing/manual-test-cases.md` 的 TTY ASK 路徑。
- 替代證據：`agent-manual-run.md`、`smoke-test.md`、`smoke-results.json`、`agent-manual-check.sh.log`。
- LIVE-01：已嘗試；因 OpenRouter chat `401 User not found` 記 **FAIL**（見 `live-01.json`）。不影響離線 SMK／MAN／Tier PASS。
- 剩餘風險：真人 UX／TTY ASK 路徑仍未由獨立人類覆核；責任版本：下一個 beta。
- 不影響：已關閉之 P0／P1 實作證據；不重開 V1-001–V1-010。
