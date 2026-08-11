## 1. Pure command analysis, classifier, and parsers

- [x] 1.1 Add typed accepted/rejected command-analysis results with canonical argv, explicit `matched_rule`, and stable `unsupported`／`unparseable`／`shell_metachar` rejection reasons; remove the unknown-to-`read` fallback.
- [x] 1.2 Implement raw shell-control detection plus one-time `shlex.split(..., posix=True)` parsing for the supported simple-command grammar, including empty/NUL and malformed-quote refusal.
- [x] 1.3 Replace broad raw-string matching with an explicit supported-command registry and category precedence; keep shell interpreters unsupported and make multipurpose executables dangerous or unsupported rather than implicitly read.
- [x] 1.4 Implement pure per-command option/path-operand adapters for at least `cat`, `ls`, `rm`, `mv`, `cp`, `touch`, and `mkdir`, including `--`, multi-source/destination arity, recursive/force `rm` escalation, and unsupported ambiguous option forms.
- [x] 1.5 Implement the pure `run_tests` args parser/schema so balanced quoted values preserve token boundaries while shell control syntax, malformed quoting, unknown options, and unmodeled path-writing options fail closed.
- [x] 1.6 Add table-driven unit tests for accepted argv/category/rule results, unknown commands, all metacharacter forms, command substitution, unbalanced quoting, dangerous precedence, command operand extraction, and pytest args parsing.
- [x] 1.7 Run `uv run pytest` and keep the full existing suite green before beginning shell-tool wiring.

## 2. `run_command`／`run_tests` wiring and integration tests

- [x] 2.1 Add or extend `WorkspaceGuard` support for validating an operand relative to an already validated execution `cwd`, including absolute paths, traversal, denied paths, and symlink escapes.
- [x] 2.2 Add a local prepared-action argv executor that resolves an executable once and calls `subprocess.run(argv, shell=False)` without serializing or reparsing the action.
- [x] 2.3 Wire `run_command` in the fixed order `cwd → analysis/classification → all path operands → canonical policy → confirmation → argv execution`, preserving deny-before-allow policy behavior and existing confirmation outcomes.
- [x] 2.4 Map every parser/containment refusal to `ToolResult(success=False)` with the specified `metadata.rejection_reason`, optional classification/rule metadata only when available, and no `exit_code`; ensure expected invalid input does not raise.
- [x] 2.5 Rebuild `run_tests` as a prepared argv action using one guarded path element plus parsed args, and route it through equivalent project-policy, explicit write classification, confirmation, timeout, and structured pytest-report handling.
- [x] 2.6 Add mocked integration tests asserting exact argv-list calls, `shell=False`, gate ordering, policy/confirmation behavior, stable refusal metadata, and zero subprocess calls for unsupported, malformed, compound-shell, denied-path, or outside-workspace inputs.
- [x] 2.7 Add real `tmp_path` integration tests for relative and absolute path operands, custom nested `cwd`, all required commands, paths beginning with `-`, and `run_tests` directories containing spaces, Unicode, quotes, and legal metacharacters.
- [x] 2.8 Add external-sentinel no-side-effect tests for traversal, symlink escape, outside `cp`／`mv` destinations, mixed valid/invalid operands, `;`／`&&`／`||`, pipelines, redirects, newlines, backticks, `$()`, and inherited-environment values; verify no file, process, or network action occurs on refusal.
- [x] 2.9 Run `uv run pytest` and keep all unit, integration, Crew wrapper, policy, confirmation, and existing regression tests green before documentation work.

## 3. Documentation, known issues, and learning log

- [x] 3.1 Update `README.md` with the supported simple-command grammar, fail-closed reasons, argv/`shell=False` behavior, path-operand coverage, `run_tests` quoting behavior, compatibility changes, and policy canonicalization notes.
- [x] 3.2 In README security limitations, distinguish what v0.9.1 improves from what it still does not guarantee: no OS sandbox/container, network/process-tree/environment isolation, general shell grammar, hostile permitted-program containment, or TOCTOU protection.
- [x] 3.3 Update `docs/releases/v1.0-alpha-known-issues.md` for V1-001／V1-002 only after linking positive, refusal, bypass, external-sentinel, and smoke evidence; retain explicit remaining containment limitations and do not imply Trust Tier or unified middleware exists.
- [x] 3.4 Append `docs/releases/learning-log-v1-prep.md` with the original bypasses, chosen canonical action model, rejected syntax/option list, compatibility impact, refusal metadata, external-sentinel and exit evidence, whitespace/special-path `run_tests` smoke results, and deferred ownership.
- [x] 3.5 Update `docs/releases/v0.9.x-handoff.md` and relevant release evidence/status references for v0.9.1, while keeping v0.9.2 dispatcher work and v1.0 Trust Tier runtime explicitly pending.
- [x] 3.6 Run `uv run pytest` after documentation updates and keep the full suite green before final verification.

## 4. Verification and OpenSpec completion

- [x] 4.1 Run `uv run pytest` and record the full passing test count plus the positive, refusal, no-side-effect, and `run_tests` whitespace-path evidence.
- [x] 4.2 Run `npx @fission-ai/openspec@latest validate --changes --strict` and resolve every active-change validation error.
- [x] 4.3 Sync the `security` and `tools` deltas into `openspec/specs/`, then run `npx @fission-ai/openspec@latest validate --specs --strict` and resolve every main-spec validation error.
- [x] 4.4 Run `./scripts/check.sh` as the final combined gate and confirm pytest plus both strict OpenSpec validation modes pass on the same revision.
- [x] 4.5 Review the diff to confirm the v0.9.1 change contains no Trust Tier, `council trust`, unified dispatcher／`SecurityContext`, OS containment, release-version bump, or unrelated v0.9.x work.
- [ ] 4.6 Archive `shell-containment` only after all tasks and evidence are complete, and verify no active delta from this change remains.
