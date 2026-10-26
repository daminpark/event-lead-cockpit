#!/usr/bin/env bash
# Install a checkout into the app container (called by the auto-deployer). Idempotent.
#   install.sh <checkout-dir> <commit-sha>
set -euo pipefail
SRC="${1:?usage: install.sh <checkout-dir> <commit-sha>}"; SHA="${2:-unknown}"
APP=/opt/gm-cockpit; DATA=/var/lib/gm-cockpit
changed() { ! cmp -s "$1" "$2"; }

id gmcockpit >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin gmcockpit
mkdir -p "$DATA" && chown gmcockpit:gmcockpit "$DATA" && chmod 750 "$DATA"

# 1. code and dependencies, prepared next to the running version
rm -rf "$APP.new" && mkdir -p "$APP.new"
cp -R "$SRC/app" "$SRC/pipeline" "$SRC/data" "$SRC/playbooks" "$SRC/scoring.toml" "$SRC/pyproject.toml" "$APP.new/"
echo "$SHA" > "$APP.new/VERSION"
chmod -R a+rX,go-w "$APP.new"
[ -d /opt/gm-cockpit-venv ] || python3 -m venv /opt/gm-cockpit-venv
/opt/gm-cockpit-venv/bin/pip install --quiet --disable-pip-version-check "fastapi>=0.115" "uvicorn>=0.30" "httpx>=0.27" "python-multipart>=0.0.9"

# 2. rebuild leads and scores from the new data before switching; a failed build leaves the old version running.
#    Reviewer decisions and settings versions in the same database are kept.
runuser -u gmcockpit -- env COCKPIT_DB="$DATA/cockpit.db" PYTHONPATH="$APP.new" /opt/gm-cockpit-venv/bin/python "$APP.new/pipeline/build.py"

rm -rf "$APP.old"; if [ -d "$APP" ]; then mv "$APP" "$APP.old"; fi
mv "$APP.new" "$APP"

# 3. services
reload=false
for unit in gm-cockpit.service gm-cockpit-autodeploy.service gm-cockpit-autodeploy.timer gm-cockpit-tunnel.service; do
  if changed "$SRC/deploy/$unit" "/etc/systemd/system/$unit"; then install -m 644 "$SRC/deploy/$unit" "/etc/systemd/system/$unit"; reload=true; fi
done
$reload && systemctl daemon-reload
systemctl enable --quiet gm-cockpit.service gm-cockpit-autodeploy.timer gm-cockpit-tunnel.service
systemctl restart gm-cockpit.service
systemctl start gm-cockpit-autodeploy.timer gm-cockpit-tunnel.service
if changed "$SRC/deploy/autodeploy.sh" /usr/local/sbin/gm-cockpit-autodeploy; then install -m 755 "$SRC/deploy/autodeploy.sh" /usr/local/sbin/gm-cockpit-autodeploy; fi

# 4. health check: if the new version doesn't come up, put the previous one back
for i in $(seq 1 20); do curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1 && { echo "healthy ($SHA)"; exit 0; }; sleep 1; done
echo "app did not become healthy; rolling back" >&2; journalctl -u gm-cockpit.service -n 20 --no-pager >&2
if [ -d "$APP.old" ]; then rm -rf "$APP.failed"; mv "$APP" "$APP.failed"; mv "$APP.old" "$APP"; systemctl restart gm-cockpit.service; fi
exit 1
