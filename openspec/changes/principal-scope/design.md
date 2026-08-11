## Context

See `proposal.md` for motivation. v0.9.4 already provides a mandatory dispatcher, immutable request context, restrict-only project policy, confirmation, and canonical audit envelopes. The remaining v0.9.5 gap is that the context identifies only requests/sessions and model calls still pass a raw `api_key` string; neither is a Council authorization identity.

The design must preserve the v0.9.2 single-dispatcher invariant and v0.9.4 audit compatibility. `run_tests` is especially important because it is one composite action that launches project code and may mutate the workspace even though it does not call a nested public tool.

## Goals / Non-Goals

**Goals:**

- Make provider model access and Council tool authority distinct in types, configuration, orchestration, and evidence.
- Give every action one deterministic cumulative scope requirement and enforce it before the private handler.
- Re-resolve current authority for each action so scope tightening, revocation, and identity substitution cannot reuse stale scopes.
- Keep scope refusals structured, correlated, auditable, sanitized, and side-effect free.
- Preserve old schema-v1 audit event verification.

**Non-Goals:**

- Prove that a principal authenticated; v0.9.6 owns authentication and step-up.
- Persist, issue, or revoke grants; v0.9.7 owns the user-controlled grant store.
- Define Trust Tier decisions or reinterpret confirmation as authority.
- Isolate project test code at the operating-system boundary.

## Decisions

### 1. Use separate immutable types for provider credentials and principals

`OpenRouterCredential` wraps the provider API key with a non-revealing representation and an explicit secret accessor used only by the OpenRouter LLM factory. Crew builders and `run_council` accept that type instead of a raw string.

`Principal` is a frozen value containing `principal_id`, `kind`, `issuer`, and a frozen set of `PrincipalScope`. It contains no provider secret, authentication token, session ID, or grant data. Runtime type checks reject crossing these boundaries.

The CLI constructs both independently: `OPENROUTER_API_KEY` becomes `OpenRouterCredential`; Council-specific identity/scope settings become a local principal. The default local principal has all v0.9.5 scopes for compatibility, but it is explicitly a local declaration, not authentication.

Alternative: derive authority from the provider API key. Rejected because provider key rotation would change Council identity, provider permissions do not describe local tool authority, and the key would contaminate audit identity.

Alternative: reuse session UUID as principal ID. Rejected because sessions are correlation records with no authentication or stable caller identity.

### 2. Define a closed scope enum and cumulative action matrix

The recognized scopes are:

| Scope | Authority |
|---|---|
| `read` | Product filesystem/list reads and the read component of shell actions |
| `filesystem:mutate` | Product filesystem mutations and any composite action allowed to mutate |
| `test` | Launch the typed pytest composite action |
| `shell` | Launch a supported command action |
| `high-risk:manage` | Proceed to policy/confirmation for dangerous shell actions |

Static tool requirements are resolved directly. `run_command` additionally uses the existing pure command analyzer before its handler to add category requirements. The handler still performs canonical parsing/path/policy/confirmation checks; repeating pure analysis does not create a second execution or authorization path.

Requirements are cumulative. `run_tests` requires `test` and `filesystem:mutate`; shell read requires `shell` and `read`; shell write requires `shell` and `filesystem:mutate`; dangerous shell requires `shell`, `filesystem:mutate`, and `high-risk:manage`. This conservative dangerous mapping prevents a high-risk/shell principal without mutate authority from using a precedence-classified command such as recursive removal.

Alternative: treat `shell` or `test` as implying every other scope. Rejected because implicit hierarchy obscures least-authority decisions and would let read-only/mutate-only combinations reach composite mutation paths.

### 3. Bind expected identity but resolve current scopes for every action

`SecurityContext` binds one expected principal identity tuple `(issuer, kind, principal_id)` and optionally a current-principal resolver. A static principal uses a resolver that returns the same immutable value. Dynamic trusted callers may supply a resolver that returns a new value with the same identity and current scopes, or `None` after revocation.

The dispatcher resolves immediately before each authorization decision:

1. no bound/current principal → deny;
2. malformed principal → deny;
3. current identity differs from the bound identity → deny;
4. missing required scopes → deny;
5. otherwise proceed to handler, where existing containment, project policy, and confirmation may further restrict.

Only scope reduction/revocation semantics are promised. The resolver is an integration seam, not a persisted grant database. v0.9.7 will define trusted storage, ownership, atomic updates, and durable revoke behavior.

Alternative: copy scopes only when the context is created. Rejected because a long execution/escalation lifecycle would retain authority after tightening or revocation.

### 4. Authorization denial precedes lower-level gates and is not tracked as execution

The dispatcher calculates principal/scope authorization before calling any private handler. Scope denial therefore occurs before workspace I/O, subprocess creation, project-policy evaluation, or confirmation prompts. Project policy and confirmation remain restrict-only later gates and can never add a missing scope.

Like unknown-context/tool-limit refusals, a scope refusal does not add an executed-operation tracker summary. With durable audit it still produces exactly one middleware-owned attempt/result pair and, when a session writer exists, one correlated denied session record.

Alternative: place scope checks in each filesystem/shell helper. Rejected because wrappers or new composite helpers could diverge and the mandatory dispatcher would no longer be the unique authority boundary.

### 5. Store authorization evidence inside existing sanitized metadata

Each middleware attempt and result receives an `authorization` metadata object:

- `principal_ref`: deterministic `sha256:` reference over issuer/kind/ID, truncated to a useful non-reversible identifier;
- recognized principal kind;
- sorted required, granted, and missing scope names;
- `scope_decision` and stable `reason`.

No raw principal ID or credential is added to result, session, or audit data. Existing recursive sanitization still runs before persistence. Authorization is stored in `metadata` rather than adding audit-envelope fields, preserving canonical verification for v0.9.4 schema-v1 records whose event IDs were computed without new top-level keys.

Alternative: store raw principal ID as a top-level audit field. Rejected because IDs can contain user/service identifiers and because adding optional top-level fields to schema v1 would change canonical reconstruction of already-written v0.9.4 events unless the audit schema were migrated.

## Risks / Trade-offs

- [Local principal declaration is not authentication] → Name and document it as an authorization input only; v0.9.6 must bind authentication evidence without treating CLI settings or `--yes` as proof.
- [Dynamic resolver is trusted in-process code] → Validate every returned principal and expected identity; do not claim hostile Python in-process isolation or durable revocation.
- [Dangerous shell matrix is intentionally conservative] → Require mutate in addition to shell/high-risk for every dangerous category until a later canonical resource/risk matrix can safely distinguish effects.
- [Existing library callers break] → Fail closed and provide an explicit migration: construct `OpenRouterCredential` and `Principal`, then pass them to `run_council`/`SecurityContext.create`.
- [Scope analysis and handler both analyze shell input] → Use the same pure analyzer and cover category agreement/no-process denial in tests; execution remains only in the private handler.

## Migration Plan

1. Add and test principal/credential values, parsing, masked references, action matrix, and decision reason codes.
2. Add principal binding/resolution and authorization evidence to the dispatcher; migrate direct test contexts to explicit full-scope test principals.
3. Replace raw provider-key parameters across model builders/orchestration and wire independent local principal resolution from CLI settings.
4. Add direct, wrapper, composite, scope-tightening/revoke, audit-redaction, and orchestrator separation tests.
5. Update compatibility/evidence documents, sync the three spec deltas, validate, archive, and run the full repository gate.

Rollback is a normal feature-commit revert. Existing audit schema-v1 files remain readable because their envelope format is unchanged.
