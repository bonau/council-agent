## Context

See `proposal.md` for motivation. In v0.9.0, `classify_command()` searches the raw command string and treats every non-match as `read`; `run_command()` then gives that string to `subprocess.run(..., shell=True)`. Classification can therefore authorize text whose meaning changes when the shell expands it. `run_tests()` compounds the problem by applying `args.split()`, joining all parts back into a string, and sending the result through the same shell path.

The existing safety order also has assets worth retaining: `WorkspaceGuard` owns workspace and denied-path checks; project policy deny precedes allow; dangerous/write actions use the confirmation gate; expected tool failures return `ToolResult` rather than raising. v0.9.1 must strengthen those paths without introducing the unified dispatcher reserved for v0.9.2.

## Goals / Non-Goals

**Goals:**

- Produce one canonical simple argv action and use it consistently for classification, policy, confirmation, path validation, and execution.
- Fail closed before process creation for unknown executables, malformed tokenization, shell control syntax, unsupported command forms, and invalid path operands.
- Execute accepted actions without a shell interpreter.
- Preserve `run_tests(path: str, args: str)` compatibility while making its final process input an argv list and allowing legal workspace paths containing spaces.
- Make every pre-execution refusal distinguishable and testable through stable metadata and no-side-effect assertions.

**Non-Goals:**

- No Trust Tier 0/1/2 behavior, `council trust`, grant model, principal, authentication, or reinterpretation of `--yes`／`ConfirmMode` as authorization.
- No unified Policy Middleware／dispatcher or `SecurityContext`; those remain v0.9.2 work.
- No OS container, bubblewrap, seccomp, chroot, network isolation, process-tree confinement, or guarantee against a permitted program's own arbitrary behavior.
- No general shell grammar. Pipelines, redirects, background jobs, command substitution, environment-assignment prefixes, and multiple commands remain unsupported.
- No policy schema/version or audit-integrity changes.

## Decisions

### 1. Analyze into a typed canonical action and reject by default

Introduce a pure command-analysis layer whose successful output contains:

- one ordered immutable `argv`;
- a `CommandCategory` (`read`, `write`, or `dangerous`);
- a non-empty `matched_rule`;
- enough command-schema information for path-operand extraction.

A rejected output contains no accepted category or executable action and carries one of the stable reasons `unsupported`, `unparseable`, or `shell_metachar`. `run_command()` maps that result to `ToolResult(success=False)` before any policy prompt or subprocess call.

Analysis order is fixed:

1. Reject empty/NUL input as `unparseable`.
2. Scan the raw command string for shell control syntax: `;`, `|`, `&`, backticks, `$`, `(`, `)`, `<`, `>`, carriage return, or newline. Reject as `shell_metachar` even when the character appears inside quotes. This deliberately chooses a small grammar over shell-compatible quoting.
3. Parse the remaining string once with `shlex.split(..., posix=True)`. A tokenization error, including unbalanced quotes, is `unparseable`.
4. Require a non-empty argv and match the executable plus supported form against an explicit command registry. No match is `unsupported`; there is no fallback `read`.
5. Apply command-specific category escalation, such as recursive/force `rm` becoming `dangerous`, before returning the action.

The initial registry explicitly covers the read and workspace-mutating commands required by the delta (`echo`, `pwd`, `cat`, `ls`, `rm`, `mv`, `cp`, `touch`, `mkdir`) and preserves intentionally supported dangerous commands from the current classifier (`sudo`, `curl`, `wget`, `chmod`, `chown`, recursive/force `rm`, `mkfs`, `dd`, `shutdown`, `reboot`). Multipurpose interpreters, launchers, and version-control commands are never inferred as read: each must be explicitly registered as dangerous with a constrained form or remain unsupported. Direct general-purpose shell interpreters (`sh`, `bash`, and equivalents) remain unsupported in v0.9.1.

Bare executable names are resolved once before execution and the resolved executable is retained in the prepared action, so lookup is not repeated after authorization. User-supplied path-qualified executables are unsupported; the one exception is a trusted executable path constructed internally for a typed action such as `run_tests`. Execution receives the retained argv, not the original command text.

Alternative considered: add an `unknown` category and pass it through confirmation. Rejected because `auto` could still turn uncertainty into execution and the requested behavior is fail-closed. Alternative considered: preserve regex classification and only set `shell=False`. Rejected because unknown programs and path-bearing forms would still inherit `read`.

### 2. Simple commands execute as argv with no shell

Accepted command text is parsed with `shlex.split`, then executed as `subprocess.run(argv, shell=False, ...)`. No stage joins argv back into executable text. A stable display/policy representation may be produced with `shlex.join(argv)`, but it is never reparsed for execution.

The prepared action, not the raw string, is passed through the remaining gates in this order:

1. resolve and validate `cwd`;
2. analyze and classify one command;
3. extract and validate all path operands;
4. evaluate project policy against the canonical action representation;
5. apply the existing confirmation gate for the category;
6. call the argv executor with the exact prepared executable and arguments.

Dangerous simple commands may still execute when existing policy and confirmation explicitly allow them, but they use `shell=False`. Shell metacharacters and compound syntax are rejected before category or confirmation, including when the input also names a dangerous command.

Alternative considered: continue `shell=True` after escaping each argument. Rejected because escaping is shell- and platform-dependent and recreates a second interpretation step. Alternative considered: support an allowlisted subset of pipelines. Rejected because v0.9.1 has one containment problem and v0.9.2 will provide the appropriate common decision boundary for future compound actions.

### 3. Path-bearing commands use command-specific operand schemas

A generic “all non-option tokens are paths” rule is insufficient because option values and source/destination arity differ. The registry therefore attaches an operand adapter to each path-bearing command:

- `cat` and `ls`: validate every file/directory operand; no operand means the validated `cwd`.
- `rm`, `touch`, and `mkdir`: validate every non-option operand.
- `mv` and `cp`: validate every source and the destination before execution.
- `--` ends option parsing and allows a path beginning with `-`.
- Only explicitly modeled short/long options are accepted. Options that consume path values must either identify and validate that value or be rejected as `unsupported`; semantics-changing forms such as an unmodeled target-directory option are never guessed.

Each relative operand is resolved against the already validated execution `cwd`, not unconditionally against workspace root. Each absolute or resulting relative candidate is then checked through `WorkspaceGuard` for root containment, symlink resolution, built-in denied paths, and active-policy denied paths. All operands are collected and validated before a process starts, so one invalid source or destination rejects the whole action.

Path failures map to `workspace_boundary` or `denied_path`. A test must pair each outside-path rejection with an external sentinel and assert both that `subprocess.run` was not called and that the sentinel is unchanged.

Alternative considered: validate only `cwd`. Rejected because an in-workspace process can name `/tmp/...` or `../...`. Alternative considered: scan all tokens that “look like paths.” Rejected because false negatives become containment bypasses and false positives break ordinary option values.

### 4. `run_tests` prepares argv directly and uses equivalent gates

Keep the public signature `run_tests(path: str = ".", args: str = "", ...)` to limit API churn:

1. Resolve `path` with `WorkspaceGuard`, verify it exists, and retain the resolved path as one argv element. Because `path` is a typed parameter rather than shell text, legal spaces, Unicode, quotes, `$`, and other filesystem characters remain literal and do not trigger command-string metacharacter scanning.
2. Scan only the raw `args` string for the same shell-control forms used by `run_command`; reject them as `shell_metachar`.
3. Parse `args` once with `shlex.split`. Unbalanced quoting is `unparseable`; tokens are never joined for execution.
4. Validate positional pytest selectors and modeled path-valued options with `WorkspaceGuard`. Maintain a conservative schema for common selection/reporting options such as `-k`, `-m`, `-q`, `-v`, `-x`, `--maxfail`, `--tb`, and `--collect-only`; reject unknown option forms as `unsupported` until their operand behavior is modeled. Path-writing options may be supported only when their destinations are explicitly identified and guarded.
5. Build the final argv as the trusted current Python executable, `-m pytest`, the one resolved test path, fixed report flags, and the parsed extra tokens.
6. Send that prepared action through the same internal policy, explicit classification, and confirmation functions as `run_command`, then through the same argv executor. The test action is classified as `write`, because test discovery/execution may create caches or project files; existing `compat` behavior still permits write actions, while `ask`／`auto`／`refuse` keep their established meanings.

This helper reuse is intentionally local to the shell tool in v0.9.1. It does not claim to be the product-wide dispatcher planned for v0.9.2.

Alternative considered: change `args` to `list[str]` immediately. Rejected because CrewAI wrappers and callers currently expose a string; one parse without rejoining removes the injection boundary while avoiding an unrelated public API migration. Alternative considered: call `run_command(shlex.join(argv))`. Rejected because that needlessly serializes a safe typed action and risks future reparsing drift.

### 5. Refusals have stable metadata and never impersonate process failures

All pre-execution shell failures return `ToolResult(success=False)` with:

- a human-readable `error`;
- `metadata.rejection_reason` set to `unsupported`, `unparseable`, `shell_metachar`, `workspace_boundary`, or `denied_path` for containment/parser refusals;
- `classification` and `matched_rule` only when analysis reached an accepted classified action;
- existing `policy_decision` or `confirmation` fields when those later gates reject;
- no `exit_code`, because no process ran.

Timeouts, OS launch errors, and non-zero exits remain execution failures and retain their existing duration/exit metadata where meaningful. Parser, guard, policy, and confirmation exceptions expected from invalid input are converted into a failure result rather than escaping.

Alternative considered: use `exit_code=126` for every refusal. Rejected because that falsely implies a process or shell attempted execution and makes no-side-effect tests ambiguous.

### 6. Verification is layered and proves absence of side effects

Implementation follows the project’s progressive-integration rule:

1. Pure analyzer, registry, metacharacter scanner, pytest-args parser, and operand adapters with table-driven unit tests. These tests cover accepted argv boundaries, every rejection reason, category precedence, option parsing, absolute/relative operands, and malformed quoting.
2. `WorkspaceGuard` operand validation and shell-tool wiring. Integration tests patch the process launcher to assert argv-list invocation with `shell=False`, exact gate order, no launch on refusals, and no partial execution.
3. Real `tmp_path` tests run allowed commands and pytest suites in directories containing spaces, Unicode, quotes, and legal metacharacters. Outside-workspace and symlink cases use sentinels and assert unchanged state. Injection cases cover `;`, `&&`, `||`, pipelines, redirect, newline, backticks, and `$()`.
4. Full regression, strict OpenSpec validation, documentation, known-issue state, and learning-log evidence.

Each implementation stage runs the full `uv run pytest` suite before advancing.

## Risks / Trade-offs

- [Existing callers rely on arbitrary shell syntax or unknown commands] → Treat the rejection as an intentional v0.9.1 compatibility break, document the supported simple grammar, and direct pytest callers to `run_tests`.
- [A narrow command/pytest-option registry initially rejects legitimate use] → Keep adapters table-driven and expand only with a path/risk model plus tests; never restore a default-read fallback.
- [POSIX `shlex` behavior differs from native Windows command-line parsing] → Define v0.9.1 input as the project’s platform-neutral POSIX-like simple grammar and test argv semantics rather than invoking a platform shell.
- [A permitted executable can itself spawn processes, access the network, interpret files, or mutate outside the workspace] → Classify multipurpose executables as dangerous or unsupported and state plainly in README/known issues that this is command-boundary hardening, not an OS sandbox.
- [Executable lookup and inherited environment remain trust inputs] → Resolve the executable once, execute that retained path, add environment-inheritance regression cases, and document that v0.9.1 does not provide environment or PATH isolation.
- [Path validation and later process access have a filesystem TOCTOU window] → Validate immediately before launch and test ordinary symlink escapes; document that adversarial concurrent filesystem mutation requires OS-level containment outside this milestone.
- [Policy patterns may observe normalized quoting rather than the caller’s original spacing] → Evaluate and display one stable canonical form, add policy regression tests for quoted paths, and document any pattern migration needed for v0.9.1.
- [`run_tests` can execute project code despite being argv-safe] → Classify it as a mutating test action and retain policy/confirmation gates; do not describe argv safety as isolation from malicious test code.

## Migration Plan

1. Land the pure analyzer and operand-schema tests while the existing executor remains unchanged; run the full test suite.
2. Replace `run_command` execution with prepared argv and add boundary/injection integration tests; run the full test suite.
3. Move `run_tests` onto the internal prepared-action executor, add whitespace/special-path and args-injection tests, then run the full suite.
4. Update README, `docs/releases/v1.0-alpha-known-issues.md`, `docs/releases/learning-log-v1-prep.md`, and the v0.9.x handoff/evidence references with exact guarantees, compatibility changes, remaining limitations, and V1-001／V1-002 evidence.
5. Run `./scripts/check.sh` and archive only after delta sync and both strict validation modes pass.

There is no persistent data migration. Rollback is a code revert, but it reopens V1-001／V1-002 and therefore must also restore their known-issue status and block v0.9.1 release claims.
