# v1.0.0-beta.4 — Release check

- 狀態：通過（local `./scripts/check.sh`；GitHub Actions 待確認無 Node 20 annotation 後才 tag）
- package：`1.0.0b4`
- tag 目標：`v1.0.0-beta.4`
- 驗證：`./scripts/check.sh`（見 `check.sh.log`）— 578 passed；specs 5/5；no active changes
- 內容：
  - GitHub Actions 離開 Node 20 runtime：`actions/checkout@v5`、`actions/setup-node@v5`、`astral-sh/setup-uv@v7`
  - OpenSpec job toolchain：Node 22（仍 ≥ 20.19）
  - 無新安全語意
- 未宣稱：獨立真人 TTY 仍 NOT-RUN；audit 仍無 predecessor hash chain
