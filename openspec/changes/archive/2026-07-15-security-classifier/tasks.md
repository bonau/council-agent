## 1. Pure classifier module + unit tests

- [x] 1.1 Create `src/council_agent/security/__init__.py` exporting `CommandCategory`, `ClassificationResult`, `classify_command`
- [x] 1.2 Implement `src/council_agent/security/classifier.py` with dangerous/write pattern tables and `classify_command`
- [x] 1.3 Add `tests/test_command_classifier.py` covering read/write/dangerous, precedence, and ROADMAP default patterns
- [x] 1.4 Run `uv run pytest tests/test_command_classifier.py` — must pass before stage 2

## 2. Wire into run_command + integration tests

- [x] 2.1 Update `run_command` in `shell.py` to classify after cwd validation and refuse `dangerous` without subprocess
- [x] 2.2 Ensure allowed commands attach `classification` in metadata; refused commands include `classification` + `matched_rule` without `exit_code`
- [x] 2.3 Add `tests/test_run_command_classification.py` for refuse/allow paths (use `tmp_path` / cross-platform commands)
- [x] 2.4 Run full `uv run pytest` — existing tests must remain green

## 3. Docs

- [x] 3.1 Update README security notice for v0.6 command classification (still not a full trust framework)
- [x] 3.2 Update `AGENTS.md` package map to include `security/` and adjust the v0.5-era ban wording

## 4. Verification

- [x] 4.1 `uv run pytest`
- [x] 4.2 `npx @fission-ai/openspec@latest validate --changes --strict`
- [x] 4.3 `npx @fission-ai/openspec@latest validate --specs --strict`
- [x] 4.4 `./scripts/check.sh`
