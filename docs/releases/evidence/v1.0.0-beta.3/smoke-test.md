# v1.0.0-beta.3 — Release check

- 狀態：通過（local `./scripts/check.sh`；GitHub Actions 待確認後才 tag）
- package：`1.0.0b3`
- tag 目標：`v1.0.0-beta.3`
- 驗證：`./scripts/check.sh`（見 `check.sh.log`）— 578 passed；specs 5/5；no active changes
- 內容：
  - 修復自 v0.9.8 起 CI `test` job 失敗：Rich 上色把 `--yes`／`--trust-tier` 拆成 `-` + `-yes`
  - 納入 develop 上的開發歷程 PDF
  - 無新安全語意
- 未宣稱：獨立真人 TTY 仍 NOT-RUN；audit 仍無 predecessor hash chain
