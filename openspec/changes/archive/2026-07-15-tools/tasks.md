## 1. Module Setup

- [x] 1.1 Create `src/council_agent/tools/` package with `__init__.py`
- [x] 1.2 Implement `tools/base.py` with `ToolResult` dataclass and `_ok`/`_err` helpers

## 2. Filesystem Tools

- [x] 2.1 Implement `read_file(path)` with UTF-8 read, size/encoding metadata
- [x] 2.2 Implement `write_file(path, content)` with auto parent dir creation, bytes_written/created metadata
- [x] 2.3 Implement `list_dir(path)` with sorted entries metadata
- [x] 2.4 Implement `delete_file(path)` for files only, deleted metadata

## 3. Shell Tool

- [x] 3.1 Implement `run_command(command, cwd, timeout_sec)` with exit_code and duration_ms metadata

## 4. Public API

- [x] 4.1 Export `ToolResult`, all tool functions from `tools/__init__.py`

## 5. Tests

- [x] 5.1 Add `tests/test_tools_filesystem.py` covering CRUD happy paths and error cases
- [x] 5.2 Add `tests/test_tools_shell.py` covering exit codes, stdout/stderr, cwd, timeout

## 6. Verification

- [x] 6.1 Run `uv run pytest` — all tests pass including existing orchestrator/preset tests
- [x] 6.2 Run `npx @fission-ai/openspec@latest validate --strict`
