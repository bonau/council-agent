#!/usr/bin/env bash
# Helper for Agents releasing a v0.9.x patch after feature branch acceptance.
# Usage: ./scripts/release-patch.sh <feature-branch> <x> "<merge summary>"
# Example: ./scripts/release-patch.sh cursor/v093-policy-trust-boundary-d691 3 "policy trust boundary"
set -euo pipefail

FEATURE_BRANCH="${1:?feature branch}"
PATCH="${2:?patch number e.g. 3}"
SUMMARY="${3:?summary}"
VERSION="0.9.${PATCH}"
PREV_PATCH=$((PATCH - 1))
PREV="0.9.${PREV_PATCH}"

echo "==> Merging ${FEATURE_BRANCH} into develop for ${VERSION}"
git fetch origin
git checkout develop
git pull origin develop
git merge --no-ff "${FEATURE_BRANCH}" -m "Merge branch '${FEATURE_BRANCH}' into develop

v${VERSION}: ${SUMMARY}."
git push origin develop

echo "==> Creating release/${VERSION}"
git checkout -b "release/${VERSION}"
python3 - "${PREV}" "${VERSION}" <<'PY'
import sys
from pathlib import Path
prev, ver = sys.argv[1], sys.argv[2]
for path, a, b in [
    (Path("pyproject.toml"), f'version = "{prev}"', f'version = "{ver}"'),
    (Path("src/council_agent/__init__.py"), f'__version__ = "{prev}"', f'__version__ = "{ver}"'),
]:
    text = path.read_text()
    if a not in text:
        raise SystemExit(f"pattern {a!r} not found in {path}")
    path.write_text(text.replace(a, b, 1))
cfg = Path("openspec/config.yaml")
cfg.write_text(cfg.read_text().replace(f"Current version: v{prev}", f"Current version: v{ver}", 1))
rm = Path("ROADMAP.md")
rm.write_text(rm.read_text().replace(f"## 現況（v{prev}）", f"## 現況（v{ver}）", 1))
print(f"bumped {prev} -> {ver}")
PY
uv lock
git add pyproject.toml src/council_agent/__init__.py openspec/config.yaml ROADMAP.md uv.lock
git commit -m "chore: release v${VERSION}"
git push -u origin "release/${VERSION}"

git checkout develop
git merge --no-ff "release/${VERSION}" -m "Merge branch 'release/${VERSION}' into develop"
git push origin develop

git checkout main
git pull origin main
git merge --no-ff "release/${VERSION}" -m "Merge branch 'release/${VERSION}'"
git tag -a "v${VERSION}" -m "v${VERSION} — ${SUMMARY}"
git push origin main
git push origin "v${VERSION}"

git checkout develop
git merge --no-ff main -m "Merge branch 'main' into develop (sync v${VERSION})" || true
git push origin develop

echo "==> Done v${VERSION}"
