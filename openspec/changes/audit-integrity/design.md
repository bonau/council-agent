## Context

See `proposal.md` for motivation. v0.9.2 made middleware the only product evidence writer and already emits request/action-correlated attempt/result pairs. v0.9.3 made project policy restrict-only and protected policy filenames, but `.council/audit/`, `.council/sessions/`, and sandbox control data are still valid `WorkspaceGuard` targets. Audit JSONL currently stores an unversioned dataclass after recursive truncation; session JSONL stores raw args, metadata, output, and error. Existing audit files must remain readable, and v1.0 owns the complete hash-chain and externally meaningful integrity claim.

## Goals / Non-Goals

**Goals:**

- Make all modeled filesystem and recognized shell path actions fail before side effects when they target current or reserved control-plane paths.
- Centralize recursive sanitization so audit, session, CLI display, and export do not diverge.
- Give each new audit record a canonical version, serialized sequence allocation, deterministic content identity, and strict structural/correlation validation.
- Preserve the exact middleware attempt identity in result and session evidence.
- Distinguish valid versioned, legacy-unverified, empty, and invalid history.

**Non-Goals:**

- No predecessor hash, signed root, external checkpoint, remote immutable sink, tail checkpoint, or claim that a host owner cannot rewrite a whole valid log.
- No authorization model in reserved auth/grant paths and no Trust Tier, principal, scope, authentication, or grant behavior.
- No transparent rewrite of historical audit or session files.

## Decisions

### 1. Protect named control-plane roots with immutable built-in patterns

`DEFAULT_DENIED_PATTERNS` remains the single base merged into every context guard. It gains root and nested forms for audit, sessions, sandbox config, and reserved auth/grant paths while retaining secrets and policy protection. Root `.council` itself remains listable so normal workspace listing semantics do not change; direct access beneath protected roots is denied. The same guard already backs filesystem operations and supported shell path operands, so no second tool-local deny mechanism is introduced.

Alternative considered: deny all of `.council/**`. That is simpler but prevents future non-control Agent workspace state and changes more behavior than this milestone requires.

### 2. Redact by field semantics and secret content before truncation

A shared sanitizer recursively copies dicts, lists, tuples, scalar fallbacks, and strings. Normalized sensitive key names mask the complete value. Text rules mask credential assignments, bearer values, JWTs, common provider prefixes, and private-key blocks even under ordinary keys such as `output` or `command`. Redaction runs before truncation and before every persistence write. Load/export also sanitize legacy data defensively.

Alternative considered: only field-name redaction. It misses secrets embedded in shell text, model output, errors, and arbitrary nested lists. Only content regexes are also insufficient because unknown token shapes stored under an explicit `api_key` field should still be fully masked.

### 3. Use a canonical per-event digest, not a chain

Schema-v1 records add `schema_version`, positive `sequence`, `event_id`, and optional `attempt_event_id`. Canonical JSON uses UTF-8, sorted keys, compact separators, and all stored fields except `event_id`; `event_id` is a prefixed SHA-256 digest of those bytes. Sequence is part of the digest. This detects field changes and gives later hash-chain code an unambiguous canonical event representation without claiming predecessor linkage or external anchoring.

Alternative considered: random UUID event IDs. UUIDs are stable references but cannot detect content changes. A predecessor digest was rejected because it would amount to partially shipping the v1.0 hash-chain contract without an anchored head, migration, or complete product semantics.

### 4. Serialize allocation and commit, then validate on read

Each audit path uses a process-local path lock plus a POSIX advisory file lock when available. Under the lock, a writer strictly parses and validates existing versioned structure, allocates the next sequence, builds the digest, and appends one newline-terminated encoded record through an append descriptor followed by `fsync`. Separate `AuditLogger` instances therefore cannot allocate the same sequence in the supported runtime. The lock file is itself inside the protected audit directory.

Structural validation rejects unsupported versions, unknown envelope fields, malformed/non-object JSON, blank record lines, missing final newline, non-contiguous sequence, duplicate IDs, and digest mismatch. Complete validation additionally rejects an orphan or mismatched result reference and dangling attempts. Writer preflight permits pending attempts because concurrent actions may interleave and because result append must follow its own attempt.

Alternative considered: derive sequence once in `AuditLogger.__init__`. Multiple logger instances and process restarts would race or reuse stale sequence values.

### 5. Result records reference the exact durable attempt

Middleware retains the `AuditRecord` returned by attempt append. Every middleware result append receives that record's `event_id`; correlation validation compares request ID, action ID, session ID, and tool. After the durable result is written, the optional session entry records both audit IDs plus request/action IDs. If attempt persistence fails, middleware returns an `audit_failure` denial before invoking the handler.

Alternative considered: continue matching only `action_id`. That detects many mistakes but does not prove which concrete attempt line a result claims and is weaker under duplication or reconstruction.

### 6. Legacy is readable but never silently verified

Records without `schema_version` load as schema 0, are recursively sanitized, and contribute `legacy_unverified` status. New schema-v1 sequence starts at 1 independently of preceding legacy lines. No automatic migration rewrites append-only history. CLI show/export reports `empty`, `verified`, or `legacy_unverified`; typed integrity failures produce a sanitized nonzero CLI result. Export is written only after source validation.

Alternative considered: reject all legacy logs. That makes a patch upgrade operationally disruptive and prevents users from extracting sanitized historical evidence. Rewriting old lines would violate append-only expectations and create unverifiable synthetic identities.

### 7. Local modes are defense in depth

Sandbox init and evidence writers request `0700` for control-plane directories and `0600` for files, reasserting modes without deleting content. These permissions reduce accidental exposure between local users where POSIX modes apply, but the documentation explicitly excludes the owning host user, root, arbitrary external processes, and project code executed by tests from the integrity claim.

## Risks / Trade-offs

- [Regex redaction can over-mask benign token-shaped text or miss a novel secret format] → combine explicit sensitive keys with conservative common formats, test false-positive ordinary values, and keep the marker/rules centralized for extension.
- [Advisory locks depend on writers cooperating] → protect all product writers and state clearly that host/external writers are outside the claim.
- [A crash after a complete attempt can leave a dangling action] → complete validation surfaces it as an integrity failure; the original attempt remains intact for operator recovery instead of being hidden.
- [Deleting the final events or replacing the entire file with a self-consistent history is not detectable without an external head] → do not claim tail completeness or tamper-proof storage; reserve anchored chaining for v1.0.
- [Legacy and v1 records in one file have different assurance] → report the whole history as `legacy_unverified`, while still structurally validating every v1 record.
- [Audit result can be durable before the session summary] → audit is the security source of truth; a missing session derivative does not invalidate the audit pair.

## Migration Plan

1. Existing sandboxes keep their files. Re-init only creates missing directories and reapplies restrictive modes.
2. The first post-upgrade event appends schema-v1 sequence 1 after any legacy lines; existing lines are never rewritten.
3. CLI reads legacy records with sanitization and reports `legacy_unverified`.
4. Rollback code can continue reading leading legacy fields from JSONL but will ignore new envelope fields only if its loader tolerates them; therefore release notes identify the audit format change. No package version is changed on this feature branch.
