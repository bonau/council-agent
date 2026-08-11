## Context

See `proposal.md` for motivation. v0.9.5 supplies stable masked principal references and a closed scope set; v0.9.6 supplies exact-action, one-use session authentication; v0.9.4 supplies canonical masked audit records. None is persistent authorization state, and project-owned policy remains restrict-only.

The store is security control-plane data, not Agent workspace data. It must therefore use host-user filesystem APIs directly under a separately validated user-data root and must not be exposed as a product tool. The implementation target is a POSIX local-user boundary where UID, modes, `O_NOFOLLOW`, advisory file locks, atomic replace, and directory `fsync` are available; unsupported ownership/locking semantics fail closed.

## Goals / Non-Goals

**Goals:**

- Persist exact self-grants and revocation tombstones across process restart without allowing project inputs to provide authority.
- Reuse the principal, authentication, and audit primitives while keeping grant administration independent from the product dispatcher.
- Make every accepted document strict, deterministic, atomically replaceable, and safe to inspect before later v0.9.8/v1.0 consumers exist.
- Provide a small authenticated CLI for operator management and evidence.

**Non-Goals:**

- No dispatcher grant gate, trust decision matrix, tier selection, wildcard/pattern grant, remote store, or shared multi-user service.
- No attempt to stop the same host user/root from editing or rolling back all user-owned state together.
- No automatic repair, schema migration, downgrade, or merge of corrupt/backup documents.

## Decisions

### Use a fixed user-data control-plane root with mandatory workspace separation

The default root is `${XDG_DATA_HOME}/council-agent/trust` when `XDG_DATA_HOME` is absolute, otherwise `~/.local/share/council-agent/trust`. A library/test override is accepted only after the same validation. The root contains fixed names:

```text
trust/
├── grants.json
├── grants.lock
└── audit/
    └── events.jsonl
```

Before I/O, the root is compared canonically with the active workspace in both ancestor directions needed to prevent overlap. Existing ancestors must be non-symlink, current-UID-owned, and not group/world writable. Store directories must be current-UID-owned mode `0700`; state, lock, and audit files must be regular current-UID-owned files mode `0600`. Newly created components use those modes and are verified after creation. A failed UID/mode/type/symlink inspection refuses the operation; the code does not silently `chmod` or take ownership of pre-existing unsafe state.

Alternative considered: `.council/grants`. Rejected because project code and Agent workspace writes are explicitly outside the authorization trust boundary.

Alternative considered: accepting arbitrary project policy or `.env` paths. Rejected because project-controlled configuration must not choose an authorization source. An explicit host/library override remains available for tests and deployments but cannot point into the workspace.

### Store one strict canonical document with retained revocation state

Schema version 1 is one canonical JSON object containing a monotonically increasing document revision and a list of grants. Each grant contains:

- opaque UUID grant ID;
- subject principal masked reference and kind;
- exact recognized top-level product action;
- canonical compact JSON resource object;
- sorted unique closed Council scopes;
- creator masked reference and kind;
- aware UTC `created_at`, optional `expires_at`;
- optional aware UTC `revoked_at` and revoker masked reference.

Grant creation is self-service in this foundation: subject and creator are the same authenticated current principal, and requested grant scopes must be a subset of that principal's current scopes. Grant/revoke additionally require `high-risk:manage`; list requires `read`. Revoked records are retained as tombstones so reopening the current document cannot resurrect them. Duplicate IDs, duplicate active exact bindings, contradictory timestamps/revokers, unknown fields/scopes/actions/schema, non-finite resource values, and malformed JSON invalidate the whole document.

Alternative considered: deleting revoked records. Rejected because a retained tombstone provides restart-persistent revocation evidence and avoids accidental in-document resurrection.

Alternative considered: wildcard actions/resources. Rejected because v0.9.7 needs exact canonical bindings; pattern authority and precedence would preempt the v0.9.8 decision matrix.

### Authenticate inside each management operation using an exact binding

Each management method builds an `AuthenticationBinding` from:

- the acting principal's masked reference;
- a masked canonical store-root reference;
- a non-empty per-invocation management session ID;
- purpose `trust-store-management`;
- a masked canonical envelope containing operation plus exact normalized arguments.

The method asks the supplied one-use provider for a token and consumes it through the supplied `AuthenticationManager`. It validates scopes and identity before mutation. CLI code creates a run-local manager/provider from typed `COUNCIL_AUTH_SECRET`; no command-line secret is accepted, and `--yes` is not part of the trust commands.

This intentionally reuses authentication primitives but not middleware invocation: trust administration is host control-plane behavior, while public product tools are Agent actions constrained to the workspace.

Alternative considered: authenticating only in CLI code. Rejected because direct library callers could bypass the boundary.

### Serialize with a validated directory descriptor and atomic replace

Mutations open the validated root directory without following symlinks, open a fixed lock file with `O_NOFOLLOW`, verify its UID/type/mode by descriptor, and hold an exclusive process lock. Under the lock they re-read and strictly validate the current document, apply exactly one mutation, increment revision, and write canonical JSON to a randomly named same-directory file opened exclusively at mode `0600`.

The writer flushes file contents, atomically replaces `grants.json` using directory-relative names, flushes the root directory, then reopens and validates the committed file before returning. Any unsupported lock implementation or I/O/validation failure is a typed fail-closed error. Reads also take a shared/exclusive serialized snapshot lock so revoke is visible to the next lookup.

Alternative considered: `Path.write_text()` in place. Rejected because crashes expose truncation and concurrent read-modify-write loses updates.

Alternative considered: SQLite. Rejected because it adds a second persistence model and migration surface for a small exact-record store; one locked canonical document is sufficient for this milestone.

### Keep lookup explicit and disconnected from Trust Tier runtime

The module exposes exact lookup for tests and the future decision matrix. Lookup canonicalizes the same action/resource, re-reads under lock, ignores revoked/expired records, verifies required scopes remain within the principal's current scopes, and returns a normalized masked decision. No field is added to `SecurityContext`, and middleware does not call the store in v0.9.7.

This closes persistent storage and revoke semantics without selecting how a grant affects allow/confirm/deny, which belongs to v0.9.8 and v1.0-alpha.

### Write trust audit under the same user-owned control plane

Trust authentication lifecycle and grant management/lookup decisions use the existing canonical audit envelope at `trust/audit/events.jsonl`, after the audit directory/file/lock pass the same ownership, permission, regular-file, and symlink checks. Grant audit metadata contains only masked principal, creator, grant, action, resource, and store references plus scope names, reason, and correlation IDs. Raw resource JSON, principal IDs, grant IDs, verifier, challenge, response, and token values never enter audit arguments or metadata.

If the audit boundary cannot be safely opened, mutation and lookup fail before returning an allowed result. Ownership/path failures that prevent safely opening the audit boundary are reported to the caller but cannot be durably recorded there.

### Recovery is explicit validation plus offline replacement

Documentation instructs users to stop Council processes, retain the current state and audit, copy with user-only permissions, run validation-only inspection, preserve the highest known revision and all newer revocations, and replace only with a supported schema. Validation never changes either source. There is no automatic merge or rollback detection against an attacker who replaces the complete user-owned control plane; that attacker is outside this local-user model.

## Risks / Trade-offs

- [The same host user/root can replace state and audit together] → State the local-user threat boundary; remote signatures/anchors are not claimed.
- [POSIX UID, no-follow, lock, and directory-flush semantics are unavailable] → Refuse grant operations rather than weakening checks.
- [Advisory locks do not constrain hostile non-cooperating writers] → Secure directory ownership excludes workspace writers; validate every descriptor and committed document.
- [Audit result persistence can fail after an atomic state commit] → Return an explicit failure and preserve pre-operation/OS evidence; never report an unaudited allow as success.
- [Expired/revoked records accumulate] → Keep them for v0.9.7 traceability; compaction requires a future authenticated, audited design.
- [Whole-control-plane backup rollback can restore older authority] → Recovery guidance forbids overwriting newer revisions/revocations; cryptographic anti-rollback is deferred.

## Migration Plan

1. Add the strict models, path boundary, locking, atomic persistence, lookup, and pure lifecycle tests.
2. Add exact management authentication and user-owned audit tests.
3. Add CLI management commands and process-restart tests using only `tmp_path` roots outside test workspaces.
4. Document backup, validation, restore, downgrade refusal, and remaining threat boundaries.
5. Rollback removes the CLI/module. Existing `trust/` data remains inert because v0.9.7 never connects it to dispatcher decisions; operators may archive it offline.
