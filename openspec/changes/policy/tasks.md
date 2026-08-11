## 1. Policy module (pure)

- [ ] 1.1 Add `src/council_agent/security/policy.py` with Pydantic `CouncilPolicy` (`allowed_commands`, `denied_commands`, `denied_paths`; ignore unknown extras), load/validate from `council.policy.yaml`, ContextVar install/reset/get, and `fnmatch`-based `evaluate_command` / effective `denied_paths` helpers
- [ ] 1.2 Export policy API from `src/council_agent/security/__init__.py`
- [ ] 1.3 Add `tests/test_policy.py` covering missing file, valid load, invalid schema, deny-over-allow, empty allowlist, and path union helpers (use `tmp_path`)
- [ ] 1.4 Run `uv run pytest tests/test_policy.py` and ensure existing suite still passes

## 2. Tools and WorkspaceGuard wiring

- [ ] 2.1 Wire `run_command` to evaluate active policy before confirmation/classification side effects that prompt; return `ToolResult(success=False)` on policy denial with clear error/metadata
- [ ] 2.2 Update `WorkspaceGuard` / `get_workspace_guard` so effective denied patterns are `DEFAULT_DENIED_PATTERNS ∪ policy.denied_paths`; clear guard cache when policy is set/reset
- [ ] 2.3 Add tests for policy-denied `run_command`, allowlist refusal, and path denial via policy patterns (`tmp_path`)
- [ ] 2.4 Run `uv run pytest` (full suite green)

## 3. Orchestrator wiring

- [ ] 3.1 In `run_council`, load `council.policy.yaml` from project/workspace root; install on success, skip if missing, fail-fast on validation error; reset in `finally`
- [ ] 3.2 Add/update tests proving invalid policy aborts before crews and valid policy is reset after run
- [ ] 3.3 Run `uv run pytest` full suite

## 4. Docs and product messaging

- [ ] 4.1 Update `README.md` with `council.policy.yaml` location, example fields, and v0.9 scope (no Trust Tier yet)
- [ ] 4.2 Update `openspec/config.yaml` context for policy capability (keep version 0.8.0 until release)

## 5. Verification

- [ ] 5.1 Run `uv run pytest`
- [ ] 5.2 Run `npx @fission-ai/openspec@latest validate --changes --strict`
- [ ] 5.3 Run `npx @fission-ai/openspec@latest validate --specs --strict`
