# Contributing to Council Agent

## Git Flow

This project follows [git-flow](https://nvie.com/posts/a-successful-git-branching-model/):

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases only |
| `develop` | Integration branch for ongoing development |
| `feature/*` | New features (one feature per branch) |
| `release/*` | Release preparation and version bumps |
| `hotfix/*` | Urgent fixes branched from `main` |

### Workflow

1. Branch `feature/<name>` from `develop`
2. Make atomic commits (see below)
3. Merge back to `develop` with `--no-ff`
4. When ready to release, branch `release/<version>` from `develop`
5. Merge `release/*` to `main` (tag) and back to `develop`

## Commit Conventions

Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`

Rules:

- One logical change per commit
- Each commit should be independently revertable
- Avoid mixing unrelated changes (e.g. crew + CLI + docs in one commit)

Examples:

```
feat(config): add pydantic settings and env loading
feat(crew): add planning crew with structured plan output
test: add preset loading unit tests
```

## Development Setup

```bash
uv sync --extra dev
cp .env.example .env   # add your OPENROUTER_API_KEY
uv run council presets list
uv run pytest
```
