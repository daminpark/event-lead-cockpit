#!/usr/bin/env bash
# Deploy now instead of waiting up to a minute: checks main is pushed, then triggers the container's auto-deployer.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source deploy/local.env
git fetch --quiet origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "HEAD isn't what's on origin/main. Commit and 'git push' first; the server deploys from GitHub."; exit 1
fi
ssh "$DEPLOY_HOST" "pct exec $DEPLOY_CT -- sh -c 'systemctl start gm-cockpit-autodeploy.service; journalctl -u gm-cockpit-autodeploy.service -n 3 --no-pager -o cat'" 2>&1 | grep -v '^locale:'
echo "Live: https://$SITE_HOST (version $(git rev-parse --short HEAD))"
