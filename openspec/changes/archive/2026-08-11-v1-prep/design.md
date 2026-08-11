## Context

See `proposal.md` for motivation. Baseline is published v0.9.0 with classifier, confirmation, audit, and project policy. Exploration (2026-08-11) found P0 conflicts with ROADMAP v1.0 DoD: shell only guards cwd, no unique middleware, classifier fail-open, project-owned policy in Agent-writable space, ConfirmMode conflated with trust, missing principal/auth, and mutable audit without integrity.

This change is documentation and process scaffolding. Runtime fixes land in later OpenSpec changes, one major issue per v0.9.x release.

## Goals / Non-Goals

**Goals:**

- Capture a durable contradiction inventory and known-issues list with responsible versions.
- Publish an Agent-executable major-release playbook and learning-log format.
- Publish smoke/public-test docs usable by humans and Agents after alpha.
- Update ROADMAP/README/LESSONS so claims match actual guarantees.
- Define alpha/beta admission gates that block Trust Tier work until P0/P1 debt is closed.

**Non-Goals:**

- Implementing shell containment, middleware, trust store, auth, or hash chain.
- Bumping package version past 0.9.0.
- Opening public beta or claiming a complete security framework.
- Merging multiple P0 fixes into one release “for speed.”

## Decisions

### D1: Preparation is a first-class OpenSpec capability (`release-prep`)
**Choice:** Add a process capability instead of `skip_specs: true`.  
**Why:** Alpha/beta gates, learning-log obligations, and “one major issue per patch” are enforceable contracts Agents must follow, not throwaway notes.  
**Alternatives:** Docs-only with `skip_specs` — rejected because validate would not encode admission rules.

### D2: Fixed v0.9.1–v0.9.9 sequence before alpha
**Choice:** Nine patches, each closing one major invariant (see learning log).  
**Why:** Dependencies are linear (containment → dispatcher → policy ownership → audit substrate → principal → auth → grants → decision matrix → evidence closure). Parallelizing invites incomplete middleware with Trust Tier bolted on.  
**Alternatives:** Fewer larger releases — rejected; harder to review and violates progressive integration.

### D3: Docs live under `docs/` with testing vs releases split
**Choice:** `docs/testing/*` for beta materials; `docs/releases/*` for playbook, learning log, known issues.  
**Why:** Testers and release Agents have different entry points; `docs/index.md` links both.  
**Alternatives:** Everything in ROADMAP — rejected; ROADMAP stays milestone-scoped.

### D4: Correct claims now; fix behavior later
**Choice:** Tighten README/ROADMAP wording in this change (filesystem vs shell; ConfirmMode ≠ Trust Tier) without changing runtime.  
**Why:** Overstated guarantees are themselves a release risk. Behavior fixes remain owned by v0.9.1+.  
**Alternatives:** Wait until code fixes — rejected; testers would rely on false claims in the meantime.

### D5: Learning log is append-only and mandatory per step
**Choice:** Fixed entry template in playbook; primary file `docs/releases/learning-log-v1-prep.md`.  
**Why:** Future Agents preparing GA need chronological decisions, failed gates, and evidence paths. Overwriting hides failures.

### D6: Smoke suite design first; executable automation in later patches
**Choice:** Document SMK cases and expected-fail shell-boundary case now; wire pytest markers/scripts when containment/middleware land.  
**Why:** Designing oracles before the P0 fix prevents “green suite that never tested the real boundary.”

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Docs drift from code while v0.9.x ships | Each patch's DoD includes updating known-issues + learning log; alpha gate re-reads inventory |
| Agents start Trust Tier early | `release-prep` scenarios + playbook hard-stop; proposal Non-goals on every v0.9.x change |
| Public testers use host home dirs | Handbook stop conditions + isolation requirements; Agent checklist forbids real secrets |
| Long patch sequence delays alpha | Sequence is dependency-driven; emergency P0 may insert a patch but must not merge two majors |
| Over-documenting unimplemented Trust Tier | Reserved sections marked “alpha only”; current ConfirmMode explicitly non-equivalent |

## Migration Plan

1. Land docs + ROADMAP/LESSONS/README claim corrections on feature branch.
2. Validate OpenSpec change; keep it active until preparation tasks complete, then archive after sync if/when `release-prep` becomes a main spec.
3. Subsequent Agents open `feature/shell-containment` (v0.9.1) etc. following the playbook—not this change's code scope.
4. Rollback: remove or revert docs/ROADMAP edits; no runtime migration.

## Open Questions

- Exact OS/container isolation technology for v0.9.1 (bubblewrap, landlock, argv-only allowlist) — deferred to the shell-containment change's design; does not alter this preparation contract.
- Whether `release-prep` remains a long-lived main capability after GA or becomes archive-only process docs — decide at v1.0 GA without blocking v0.9.x.
