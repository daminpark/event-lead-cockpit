#!/usr/bin/env bash
# Refresh the public copy (github.com/daminpark/event-lead-cockpit): the same commits, dates and messages,
# minus the files that name people. The private repo stays the one that deploys.
#   ./deploy/publish.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PUBLIC="${PUBLIC_REPO:-https://github.com/daminpark/event-lead-cockpit.git}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone --quiet --no-local . "$tmp/repo"
cd "$tmp/repo"
uvx --quiet git-filter-repo --quiet --force --invert-paths \
  --path data/extracted --path data/briefs --path data/source_checks.json
# nothing that names a person may be left in any commit
if git log --all --name-only --format= | grep -qE '^data/(extracted|briefs)/|source_checks'; then
  echo "people data still present; not publishing" >&2; exit 1
fi
git remote add public "$PUBLIC"
git push --quiet --force public HEAD:main
echo "public copy updated: ${PUBLIC%.git} ($(git rev-list --count HEAD) commits)"
