# v1.0.0-beta.1 — Smoke / Agent re-run

- 狀態：通過
- 基準：commit `dd4d99fe9135ac255601e43f0e6a6ea2279e12b9`、package `1.0.0a1`、tag `v1.0.0-alpha.1`
- `./scripts/check.sh`：577 passed；no active changes；specs 5/5（見 `check.sh.log`）
- Tier／grant／shell vectors：見 `beta-smoke.json`（全部 PASS；sentinel 不變）
- LIVE-01：BLOCKED（無核准 provider credential）
- 真人手冊：維持 admission ACCEPTED GATE（見 alpha `human-manual-status.md`）；本環境無獨立真人
