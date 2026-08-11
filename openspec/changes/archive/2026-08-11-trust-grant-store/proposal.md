## Why

Council has principal and session-authentication foundations, but it still has no persistent authorization source that a workspace Agent cannot write or restore. v0.9.7 must close V1-008 before a later decision matrix or Trust Tier runtime can safely consume grants.

## What Changes

- Add a schema-versioned user-owned trust grant store outside the workspace, with strict ownership, permission, symlink, and workspace-separation checks that fail closed.
- Add exact grant records bound to a Council principal, canonical action and resource, closed scopes, creator, creation time, optional expiry, and unique ID.
- Require fresh exact-operation authentication and existing principal scopes for grant, revoke, and list administration; project policy, confirmation, `--yes`, and Agent workspace writes cannot create or expand authority.
- Make revocation persistent and immediately visible to the next lookup; reject expired, revoked, duplicate, conflicting, malformed, and unknown-schema state.
- Serialize concurrent mutations and commit same-directory temporary files with atomic replace, durable flush, and restrictive permissions.
- Emit correlated, masked audit evidence for management and lookup decisions.
- Add the foundational `council trust grant`, `revoke`, and `list` commands without connecting grants to Trust Tier runtime decisions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `security`: Define the user-owned trust grant model, storage boundary, validation, lifecycle, atomicity, authentication, and masked evidence contracts.
- `orchestration`: Define the local CLI management boundary for authenticated grant, revoke, and list operations without enabling Trust Tier runtime.

## Impact

- Adds a focused module under `src/council_agent/security/`, security exports, and grant-store unit tests.
- Adds a `trust` Typer command group and CLI integration tests.
- Adds no third-party dependency and does not alter the product tool dispatcher or grant tool authority at runtime.
- Adds user-owned local data under the platform user data root, defaulting to `${XDG_DATA_HOME:-~/.local/share}/council-agent/trust/`.

## Non-goals

- Trust Tier 0/1/2 runtime behavior, a trust decision matrix, or grant consumption by the dispatcher.
- A `--trust-tier` option or treating `ConfirmMode.AUTO` / `--yes` as authentication or a persistent grant.
- Remote synchronization, shared repository grants, team IAM, SSO, OAuth, or WebAuthn.
- Package version bump, release tag, or release-branch work.
- Protection from a hostile in-process Python caller, the host owner/root, rollback of all user-owned files as one snapshot, or an OS-level attacker.
