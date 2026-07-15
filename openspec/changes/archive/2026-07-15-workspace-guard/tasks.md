## 1. OpenSpec & Branch

- [x] 1.1 Create `feature/workspace-guard` branch and OpenSpec change artifacts

## 2. WorkspaceGuard Core

- [x] 2.1 Create `src/council_agent/sandbox/` package with `workspace.py`
- [x] 2.2 Implement `WorkspaceGuard`, `WorkspaceGuardError`, `resolve()`, `resolve_cwd()`, denylist
- [x] 2.3 Add `council_workspace_root` to `Settings` and `get_workspace_guard()` singleton
- [x] 2.4 Update `.env.example` with `COUNCIL_WORKSPACE_ROOT`

## 3. Tool Integration

- [x] 3.1 Integrate guard into `filesystem.py` (read, write, list, delete)
- [x] 3.2 Integrate guard into `shell.py` (`run_command` cwd validation)

## 4. Tests

- [x] 4.1 Add `tests/conftest.py` with autouse workspace root fixture
- [x] 4.2 Add `tests/test_workspace_guard.py` (traversal, symlink, denylist)
- [x] 4.3 Add `tests/test_tools_workspace_integration.py`
- [x] 4.4 Verify existing tool tests pass with fixture

## 5. Verification & Release

- [x] 5.1 Run `uv run pytest` — all tests pass
- [x] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [x] 5.3 Archive change and bump version to 0.3.0
