## Why

Verification FAIL 後現行 escalation 會替換最終輸出，卻保留前一次 verdict，且 escalation 的 tool／decision／audit evidence 沒有獨立 attempt 邊界；這使 V1-010／SEC-P1-002 無法證明最終結果真的符合原成功標準。v0.9.9 也必須把 v0.9.x 公開文件從歷史 v0.9.0 限制校正到實際 v0.9.8 邊界，完成進入 v1.0-alpha 前的最後一筆清債。

## What Changes

- 為 initial execution 與每次 escalation 建立可追溯 attempt ID，保留每次 execution、tool summaries、verification verdict 與停止原因。
- 依 `max_retries` 執行 escalation，且每次都以原 plan／success criteria 重新 Verification；重試耗盡仍失敗時最終 verdict 保持 FAIL。
- 將 escalation 接到既有 Execution Crew tools，並以 attempt 邊界切分 tracker summaries；tool decision、request/action 與 audit/session evidence 帶同一 attempt correlation。
- Verification 增加 deterministic evidence gate：成功條件要求 tool／pytest 證據時，缺少、跨 attempt、失敗或結構不完整的證據不得被 LLM verdict 判成 PASS。
- 新增 v0.9.9 evidence，校正 ROADMAP、README、known issues、handoff 與公開測試文件，使已具能力、啟發式限制、OS containment 非目標及 Trust Tier 停止線一致。

## Capabilities

### New Capabilities

- （無）

### Modified Capabilities

- `orchestration`: 定義 attempt-scoped execution／escalation、重驗證、最終 evidence 一致性與 fail-closed Verification evidence gate。
- `security`: 將 pipeline attempt correlation 加入既有 dispatcher-owned tool decision 與 durable audit evidence，不建立第二條決策路徑。
- `sandbox`: session tool evidence 保留 pipeline attempt correlation，且舊 attempt evidence append-only 保留。
- `release-prep`: 校正 v0.9.9 關閉條件、公開測試文件與 v1.0-alpha 停止／交接規則。

## Impact

- 受影響程式：`src/council_agent/types.py`、`orchestrator.py`、execution／verification crews、security middleware 與 session evidence。
- 受影響測試：orchestrator retry／final alignment、verification evidence gate、dispatcher audit/session attempt correlation 與 escalation tool wiring。
- 受影響文件：`README.md`、`ROADMAP.md`、`docs/releases/`、`docs/testing/` 與對應 main specs。
- 不新增 dependency，不變更套件版本。

## Non-goals

- 不實作或啟用 Trust Tier 0/1/2 runtime、tier translator、`--trust-tier` 或 persisted grant consumption。
- 不交付任何 v1.0-alpha 功能；v1.0-alpha Trust Tier 必須另開獨立 OpenSpec change。
- 不做版本 bump、release branch、tag 或發佈。
- 不宣稱 tool path boundary 是 OS／container sandbox，也不把 per-event audit integrity substrate 宣稱為 externally anchored hash chain。
