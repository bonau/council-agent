## REMOVED Requirements

### Requirement: No workspace boundary enforcement

**Reason**: v0.3 introduces WorkspaceGuard; all tool path and cwd operations must be validated.
**Migration**: Tool functions now call `WorkspaceGuard.resolve()` or `resolve_cwd()` at entry; paths outside workspace return `success=False`.

## ADDED Requirements

### Requirement: Workspace boundary enforcement on filesystem tools

All filesystem tool functions (`read_file`, `write_file`, `list_dir`, `delete_file`) SHALL validate the `path` argument via `WorkspaceGuard.resolve()` before performing any file operation. When validation fails, they SHALL return `ToolResult(success=False, error=<message>)` without raising.

#### Scenario: Filesystem tool rejects path outside workspace

- **WHEN** `read_file` is called with a path that resolves outside the workspace root
- **THEN** it returns `success=False` with an error message about workspace boundary

#### Scenario: Filesystem tool rejects denied path

- **WHEN** `read_file` is called with path `.env`
- **THEN** it returns `success=False` with an error message about denied path

#### Scenario: Filesystem tool allows valid workspace path

- **WHEN** `write_file` is called with a path inside the workspace and not denied
- **THEN** it proceeds with the write operation as before

### Requirement: Workspace boundary enforcement on run_command

The `run_command` tool SHALL validate the `cwd` argument via `WorkspaceGuard.resolve_cwd()` before executing. When `cwd` is `None`, the command SHALL execute with workspace root as working directory.

#### Scenario: run_command rejects cwd outside workspace

- **WHEN** `run_command` is called with `cwd` pointing outside the workspace root
- **THEN** it returns `success=False` with an error message about workspace boundary

#### Scenario: run_command defaults to workspace root

- **WHEN** `run_command` is called without `cwd`
- **THEN** the command executes with workspace root as the working directory
