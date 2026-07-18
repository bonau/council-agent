## 1. Confirmation module (pure)

- [x] 1.1 Add `src/council_agent/security/confirm.py` with `ConfirmMode`, policy ContextVar, `require_confirmation`, default Rich `confirm_fn`, and install/reset helpers
- [x] 1.2 Export confirmation API from `src/council_agent/security/__init__.py`
- [x] 1.3 Add `tests/test_confirmation.py` covering `compat` / `ask` / `auto` / `refuse` (mock `confirm_fn`)
- [x] 1.4 Run `uv run pytest tests/test_confirmation.py` and ensure existing suite still passes

## 2. Tools confirmation gates

- [x] 2.1 Gate `run_command` for `dangerous` and `write` via confirmation; include `confirmation` in metadata; preserve no-subprocess on deny
- [x] 2.2 Gate `write_file` and `delete_file` after WorkspaceGuard resolve; leave `read_file` / `list_dir` ungated
- [x] 2.3 Add/update tests: `tests/test_run_command_classification.py` (and new filesystem confirmation tests) proving refuse/auto/ask and no side effects on deny
- [x] 2.4 Run `uv run pytest` for tools/security tests (full suite green under default `compat`)

## 3. CLI and orchestrator wiring

- [x] 3.1 Add `confirm_mode` (and optional confirm_fn) to `run_council`; install policy in try/finally
- [x] 3.2 Add `council run --yes`; resolve mode from `--yes` + `sys.stdin.isatty()`; pass into `run_council`
- [x] 3.3 Add tests for mode resolution and orchestrator policy install/reset
- [x] 3.4 Run `uv run pytest` full suite

## 4. Docs and product messaging

- [x] 4.1 Update `README.md` security note and `--yes` usage
- [x] 4.2 Update `openspec/config.yaml` context for confirmation capability (keep version 0.6.0 until release)

## 5. Verification

- [x] 5.1 Run `uv run pytest`
- [x] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [x] 5.3 Run `npx @fission-ai/openspec@latest validate --specs --strict`
