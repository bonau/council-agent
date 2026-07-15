# Contributing to Council Agent

## Development Methodology

本專案採 **Spec-driven Development**，並以 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理規格與變更。所有新功能、修正與重構，應先建立 OpenSpec change，對齊規格後再實作。

### 工作流程

1. **探索**（需求不明）→ `/opsx:explore`
2. **提案** → `/opsx:propose "<change-name>"` 產生 proposal、design、tasks、spec delta
3. **審閱** → 確認 artifacts 無誤
4. **實作** → `/opsx:apply`，依 tasks.md 逐步完成
5. **驗證** → 執行下方 Definition of Done 中的驗證指令
6. **歸檔** → `/opsx:archive` 將 delta 合併至 `openspec/specs/`

### Definition of Done

完成 change 或準備發版前，確認：

- [ ] `tasks.md` 全部 `[x]`
- [ ] delta 已 sync 至 `openspec/specs/`
- [ ] change 已 archive（發版時應無 active change）
- [ ] `uv run pytest` 全過
- [ ] `npx @fission-ai/openspec@latest validate --changes --strict`
- [ ] `npx @fission-ai/openspec@latest validate --specs --strict`

發版額外項目（見 [LESSONS.md](LESSONS.md)）：

- [ ] `pyproject.toml` 與 `src/council_agent/__init__.py` 版本一致
- [ ] `release/<version>` 合併至 `main` 並打 tag
- [ ] `release/<version>` 以 `--no-ff` 合併回 `develop`

### 環境需求

OpenSpec CLI 需要 Node.js ≥ 20.19：

```bash
npx @fission-ai/openspec@latest --version
```

詳細說明見 [AGENTS.md](AGENTS.md)。

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
