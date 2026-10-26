#!/usr/bin/env bash
# Pull-based deploy, run every minute by gm-cockpit-autodeploy.timer inside the app container.
# If main on GitHub has a new commit, check it out and run deploy/install.sh from it.
set -euo pipefail
REPO_URL="${REPO_URL:?set REPO_URL in /etc/default/gm-cockpit-autodeploy}"; BRANCH="${BRANCH:-main}"
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -i /root/.ssh/gm_deploy -o IdentitiesOnly=yes}"
SRC=/opt/gm-cockpit-src; STATE=/var/lib/gm-cockpit-autodeploy
mkdir -p "$STATE"
[ -d "$SRC/.git" ] || git clone --quiet --branch "$BRANCH" "$REPO_URL" "$SRC"
git -C "$SRC" fetch --quiet --prune origin "$BRANCH"
NEW="$(git -C "$SRC" rev-parse "origin/$BRANCH")"
[ "$NEW" = "$(cat "$STATE/deployed" 2>/dev/null)" ] && exit 0
[ "$NEW" = "$(cat "$STATE/failed" 2>/dev/null)" ] && exit 0   # don't retry a broken commit every minute
git -C "$SRC" reset --quiet --hard "$NEW" && git -C "$SRC" clean -fdq
if bash "$SRC/deploy/install.sh" "$SRC" "$NEW"; then
  echo "$NEW" > "$STATE/deployed"; rm -f "$STATE/failed"
  echo "deployed $NEW: $(git -C "$SRC" log -1 --format=%s "$NEW")"
else
  echo "$NEW" > "$STATE/failed"
  echo "deploy of $NEW failed; still serving $(cat "$STATE/deployed" 2>/dev/null || echo 'the previous version')" >&2
  exit 1
fi
