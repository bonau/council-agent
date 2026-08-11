## 1. Audit module (pure)

- [ ] 1.1 Add `src/council_agent/security/audit.py` with `AuditRecord`, `AuditLogger` (append-only JSONL), argument truncation, ContextVar install/reset/`record_audit_event` no-op when unset
- [ ] 1.2 Add `audit_dir` helper (or equivalent) in sandbox config; ensure `init_sandbox` creates `.council/audit/` idempotently without deleting events
- [ ] 1.3 Export audit API from `src/council_agent/security/__init__.py`
- [ ] 1.4 Add `tests/test_audit.py` covering append, no-op without logger, truncation, re-init preserves events (use `tmp_path`)
- [ ] 1.5 Run `uv run pytest tests/test_audit.py` and ensure existing suite still passes

## 2. Execution / orchestrator wiring

- [ ] 2.1 In `crews/execution_tools._invoke`, after a tracked tool result, call `record_audit_event` with tool name, args, success/error/metadata, and session id when present
- [ ] 2.2 In `run_council`, when sandbox session project is available, install `AuditLogger` for the run (session id bound) and reset in `finally`
- [ ] 2.3 Add/update tests proving sandboxed tool invocations append audit events and logger is cleared after run
- [ ] 2.4 Run `uv run pytest` (full suite green)

## 3. CLI audit show / export

- [ ] 3.1 Add `council audit show` (limit, optional `--session`, `--workspace`) reading `.council/audit/events.jsonl`
- [ ] 3.2 Add `council audit export` writing JSONL to a user path with optional session filter
- [ ] 3.3 Add CLI/integration tests for show (empty + populated) and export (all + filtered)
- [ ] 3.4 Run `uv run pytest` full suite

## 4. Docs and product messaging

- [ ] 4.1 Update `README.md` with audit log location and `council audit show` / `export` usage
- [ ] 4.2 Update `openspec/config.yaml` context for audit capability (keep version 0.7.0 until release)

## 5. Verification

- [ ] 5.1 Run `uv run pytest`
- [ ] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [ ] 5.3 Run `npx @fission-ai/openspec@latest validate --specs --strict`
