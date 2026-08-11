## Context

See `proposal.md` for motivation. v0.9.2 already loads one project policy before crews and stores it in an immutable `SecurityContext`, but the policy model has `extra="ignore"`, no schema discriminator, and a temporary `policy_version="v0.9-unversioned"` label. `WorkspaceGuard` unions project `denied_paths` with built-in entries, while `council.policy.yaml` itself is not built-in protected.

The implementation must preserve the v0.9.1 canonical-command boundary and v0.9.2 single-dispatcher lifecycle. It must not add an authorization source: the project file lives inside the untrusted workspace and can only reduce the actions otherwise admitted by built-in and future user-owned controls.

## Goals / Non-Goals

**Goals:**

- Define one explicit project-policy schema version with deterministic reject/migrate behavior.
- Reject unknown, misspelled, authorization-shaped, and ill-typed fields without leaking their values in diagnostics.
- Encode restrict-only semantics in the accepted field set, evaluation precedence, specs, and tests.
- Derive the middleware snapshot label from the validated policy rather than accepting an unrelated label.
- Block supported product tools from directly accessing root or nested project policy files and prove refusal has no side effects.

**Non-Goals:**

- A user-owned policy/grant storage API, ownership checks, grant/revoke lifecycle, or trust-store persistence.
- Principal, scope, session authentication, Trust Tier, or confirmation-policy redesign.
- Audit control-plane integrity, redaction, sequence, hash chain, or OS-level filesystem isolation.
- Preventing project code executed by `run_tests`, a hostile host user, or an out-of-process actor from mutating workspace files.

## Decisions

### 1. Schema version 1 is a required integer discriminator

Version 1 uses:

```yaml
schema_version: 1
allowed_commands: []
denied_commands: []
denied_paths: []
```

The policy model uses strict validation and forbids extras. `schema_version` is required and accepts only integer `1` (not `"1"`, `1.0`, or `true`). Keeping the discriminator exact avoids YAML coercion and ambiguous compatibility. Lists contain strings only; no future authorization-shaped field is accepted speculatively.

Alternatives:

- A string such as `"1.0"`: rejected because this schema has no negotiated minor-version compatibility and an integer gives one canonical YAML representation.
- Defaulting a missing version to 1: rejected because legacy files would silently cross a security schema boundary.
- Keeping `extra="ignore"` for forward compatibility: rejected because an older runtime must not silently ignore a new security restriction or authorization field.

### 2. Legacy unversioned files fail with an explicit one-line migration

A present file without `schema_version` is rejected before model validation with a diagnostic that names the path and says to add `schema_version: 1`. Unsupported or wrong-typed versions are rejected before any other field is applied. There is no compatibility mode, warning-only path, or partial fallback; absence of the whole file remains valid and means built-in defaults.

Rollback is an ordinary code revert before release. After release, users migrate by adding the discriminator and removing every unsupported field; fields such as `trust_tier` or `max_tool_calls` cannot remain as inert placeholders.

### 3. Validation diagnostics expose locations, not input values

The loader converts validation failures into a stable summary containing the policy path plus each error location and category/message while omitting Pydantic's `input` and context payloads. Missing/unsupported version diagnostics state the observed value only when it is the scalar schema discriminator; arbitrary unknown field values are never interpolated.

This preserves useful typo diagnostics such as `denied_command: extra field forbidden` without echoing an `api_key`, token, grant, or other secret-looking value.

### 4. Restrict-only is enforced by a closed field set and deny precedence

Version 1 accepts only three restriction collections:

- a non-empty `allowed_commands` is an additional allowlist filter (intersection with actions admitted by command analysis and later gates);
- `denied_commands` is checked first and adds hard command denials;
- `denied_paths` is unioned with built-in path denials.

No accepted field can remove a default denial, skip classification/containment/confirmation, create a principal or grant, or select a tier. A matching allow pattern means only “project filter passed”; it is never a positive authorization result. Tests pair an allow match with built-in unsupported and confirmation-denied cases to prove this precedence.

Alternatives:

- Remove `allowed_commands` because of its positive name: rejected because its existing non-empty allowlist semantics already narrow authority and are useful when documented as an intersection.
- Add explicit `grants: []` reserved fields: rejected because accepting the shape would blur the v0.9.7 user-owned boundary and encourage unsafe workspace storage.

### 5. The middleware owns the schema snapshot label

`SecurityContext.create()` derives `policy_version` from its policy snapshot:

- no project file: `builtin`;
- version 1 project policy: `project-policy/v1`.

Context validation checks that the label matches the snapshot, preventing a caller or later derived view from pairing a policy object with a stale/unrelated schema label. The existing middleware correlation metadata continues to copy this label to every result/audit record.

### 6. Built-in path denial protects policy files on supported tool paths

`WorkspaceGuard` built-in patterns add both the root filename and a nested pattern so a context protects `council.policy.yaml` whether the resolved project root equals the workspace root or is below it. Since built-in and project patterns are unioned, the policy cannot remove this protection or edit itself through `read_file`, `write_file`, `delete_file`, or a supported shell command with a recognized path operand.

The guard still permits listing a parent directory; listing can reveal the filename but not read or mutate it. `run_tests` executes project code and is not an OS sandbox, so documentation and evidence explicitly state that malicious tests or external actors can still write the file. v0.9.4 may protect additional control-plane resources, but this change does not overstate the current boundary.

## Risks / Trade-offs

- [Existing unversioned policies stop all runs] → provide a minimal migration example, a specific missing-version error, and release/handoff notes.
- [Strict extras reject users who predeclared future fields] → document that this is intentional fail-fast behavior; future schema versions require an explicit runtime upgrade/migration.
- [Policy filename deny blocks direct tool reads useful for editing] → treat policy as project-owned control input edited by the host/user outside Agent product tools; parent listing remains available.
- [Filename patterns cannot stop arbitrary executed code] → scope claims to supported product filesystem/modeled shell paths and retain the `run_tests`/OS-containment warning.
- [Programmatic callers construct policy models directly] → update test/caller fixtures to pass schema version 1 and export named schema/label constants.

## Migration Plan

1. Add strict schema/version parsing and focused loader/evaluator tests; run the full test suite.
2. Derive and validate the middleware snapshot label; update orchestrator fail-fast tests; run the full test suite.
3. Add built-in root/nested policy path protection and public-tool no-side-effect tests; run the full test suite.
4. Update README, migration/evidence/release documents and OpenSpec deltas.
5. Sync main specs, validate both changes and specs, archive, then run the post-archive full gate.

Existing file migration:

```yaml
# Before (rejected)
denied_commands:
  - "curl *"

# After
schema_version: 1
denied_commands:
  - "curl *"
```

No persisted authorization or grant data is created, so rollback has no trust-store migration.
