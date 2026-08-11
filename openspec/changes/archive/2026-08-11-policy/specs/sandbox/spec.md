## ADDED Requirements

### Requirement: WorkspaceGuard merges policy denied paths

When an active policy provides `denied_paths`, `WorkspaceGuard` path validation SHALL reject paths matching either the built-in default sensitive denylist or any pattern from the policy `denied_paths` list (union). Built-in defaults SHALL remain in effect even when a policy file is present. Policy patterns SHALL use the same matching semantics as the existing sensitive-path denylist (including `/**` directory prefixes and basename-style patterns).

#### Scenario: Policy denied path is blocked

- **WHEN** the active policy includes `denied_paths` with `secrets/**` and `resolve` is called with `secrets/token.txt`
- **THEN** access is denied as a sensitive path

#### Scenario: Default denylist still applies with policy

- **WHEN** a policy file is active that does not list `.env` in `denied_paths` and `resolve` is called with `.env`
- **THEN** access is still denied by the built-in default denylist

#### Scenario: No policy adds no extra path denials

- **WHEN** no policy is installed
- **THEN** path validation uses only the built-in default denylist patterns
