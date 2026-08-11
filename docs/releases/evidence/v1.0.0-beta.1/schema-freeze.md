# v1.0.0-beta.1 — Schema freeze

Frozen at tag baseline `v1.0.0-alpha.1` / package `1.0.0a1` (beta release will bump to `1.0.0b1`).

| Contract | Frozen value |
|----------|--------------|
| Trust Tier | `0` / `1` / `2` via CLI `--trust-tier` and `SecurityContext.trust_tier` |
| Decision matrix | version **2** (same six dimensions; read may use interaction) |
| Principal scopes | `read`, `filesystem:mutate`, `test`, `shell`, `high-risk:manage` |
| Grant store schema | v1 exact-binding user-owned store |
| Session authentication | process-local challenge/token; high-risk step-up; Tier 2 selection step-up |
| Audit | schema-v1 sequenced per-event identity + redaction (no predecessor hash chain) |
| Project policy | schema_version `1` restrict-only; **no** `trust_tier` field |

Beta accepts only blocking fixes, compatibility fixes, tests, and documentation. New security semantics require a new alpha.
