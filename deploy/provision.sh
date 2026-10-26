#!/usr/bin/env bash
# One-time setup of the app container on Proxmox, run from this Mac. Safe to re-run: each step
# checks what is already there. Needs deploy/local.env, ~/.cloudflared/cert.pem and gh signed in.
#   ./deploy/provision.sh           # everything
#   ./deploy/provision.sh secrets   # re-copy HUBSPOT_TOKEN / OPENROUTER_API_KEY / COCKPIT_CODE from deploy/local.env
#   ./deploy/provision.sh <step>    # one step: container, packages, tunnel, deploy_key, secrets, first_deploy
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source deploy/local.env
CT="$DEPLOY_CT"; HOST="$DEPLOY_HOST"; STEP="${1:-all}"
REPO_SSH="${REPO_SSH:-git@github.com:daminpark/generalmind-cockpit.git}"
in_ct() { ssh "$HOST" "pct exec $CT -- bash -c $(printf %q "$1")"; }
say() { printf '\n== %s\n' "$1"; }

container() {
  say "container $CT"
  if ssh "$HOST" "pct status $CT" >/dev/null 2>&1; then echo "exists"; return; fi
  ssh "$HOST" "pct create $CT local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
    --hostname berlin-gm-leads --cores 1 --memory 512 --swap 256 --rootfs local-lvm:4 \
    --net0 name=eth0,bridge=vmbr0,ip=dhcp,ip6=auto --nameserver '1.1.1.1 1.0.0.1' \
    --unprivileged 1 --features nesting=1 --onboot 1 \
    --description 'GeneralMind event lead cockpit (case study) served at $SITE_HOST via Cloudflare Tunnel'"
  ssh "$HOST" "pct start $CT"
  sleep 10
}

packages() {
  say "packages"
  in_ct "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3 python3-venv curl ca-certificates openssh-client >/dev/null && echo installed"
  # The router's DNS mangles Cloudflare's tunnel lookups; keep the container on 1.1.1.1 even after DHCP renews.
  in_ct "grep -q '^supersede domain-name-servers' /etc/dhcp/dhclient.conf || echo 'supersede domain-name-servers 1.1.1.1, 1.0.0.1;' >> /etc/dhcp/dhclient.conf; printf 'nameserver 1.1.1.1\\nnameserver 1.0.0.1\\n' > /etc/resolv.conf"
  in_ct "command -v cloudflared >/dev/null || (curl -fsSL -o /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && dpkg -i /tmp/cloudflared.deb >/dev/null && rm /tmp/cloudflared.deb); cloudflared --version"
}

tunnel() {
  say "tunnel $TUNNEL_NAME -> $SITE_HOST"
  id="$(cloudflared tunnel list -o json 2>/dev/null | python3 -c "import json,sys; print(next((t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'), ''))")"
  if [ -z "$id" ]; then
    cloudflared tunnel create "$TUNNEL_NAME" >/dev/null
    id="$(cloudflared tunnel list -o json | python3 -c "import json,sys; print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'))")"
  fi
  cloudflared tunnel route dns "$TUNNEL_NAME" "$SITE_HOST" 2>&1 | tail -1 || true
  in_ct "id cloudflared >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin cloudflared; mkdir -p /etc/cloudflared"
  ssh "$HOST" "pct exec $CT -- sh -c 'cat > /etc/cloudflared/$id.json'" < "$HOME/.cloudflared/$id.json"
  printf 'tunnel: %s\ncredentials-file: /etc/cloudflared/%s.json\nno-autoupdate: true\ningress:\n  - hostname: %s\n    service: http://127.0.0.1:8080\n  - service: http_status:404\n' "$id" "$id" "$SITE_HOST" \
    | ssh "$HOST" "pct exec $CT -- sh -c 'cat > /etc/cloudflared/config.yml'"
  in_ct "chown -R cloudflared:cloudflared /etc/cloudflared && chmod 600 /etc/cloudflared/*.json && echo 'tunnel $id configured'"
}

deploy_key() {
  say "GitHub deploy key"
  in_ct "mkdir -p /root/.ssh && test -f /root/.ssh/gm_deploy || ssh-keygen -q -t ed25519 -N '' -C 'berlin-gm-leads deploy' -f /root/.ssh/gm_deploy"
  in_ct "ssh-keyscan -t ed25519 github.com 2>/dev/null >> /root/.ssh/known_hosts; sort -u -o /root/.ssh/known_hosts /root/.ssh/known_hosts"
  key="$(in_ct 'cat /root/.ssh/gm_deploy.pub')"
  repo="${REPO_SSH#git@github.com:}"; repo="${repo%.git}"
  if gh repo deploy-key list --repo "$repo" | grep -q 'berlin-gm-leads'; then echo "already added"; else
    printf '%s\n' "$key" > /tmp/gm_deploy.pub
    gh repo deploy-key add /tmp/gm_deploy.pub --repo "$repo" --title "berlin-gm-leads (read-only)"
    rm /tmp/gm_deploy.pub
  fi
  printf 'REPO_URL=%s\nBRANCH=main\n' "$REPO_SSH" | ssh "$HOST" "pct exec $CT -- sh -c 'cat > /etc/default/gm-cockpit-autodeploy'"
}

secrets() {
  say "secrets"
  # Only these keys leave the Mac, and they are never printed.
  grep -E '^(HUBSPOT_TOKEN|OPENROUTER_API_KEY|COCKPIT_CODE|COCKPIT_OWNER_CODE)=' deploy/local.env \
    | ssh "$HOST" "pct exec $CT -- sh -c 'umask 077; cat > /etc/default/gm-cockpit'"
  in_ct "systemctl restart gm-cockpit.service 2>/dev/null || true; echo saved"
}

first_deploy() {
  say "first deploy"
  in_ct "test -x /usr/local/sbin/gm-cockpit-autodeploy || { GIT_SSH_COMMAND='ssh -i /root/.ssh/gm_deploy -o IdentitiesOnly=yes' git clone --quiet --depth 1 $REPO_SSH /tmp/gm-bootstrap; install -m 755 /tmp/gm-bootstrap/deploy/autodeploy.sh /usr/local/sbin/gm-cockpit-autodeploy; rm -rf /tmp/gm-bootstrap; }"
  in_ct "set -a; . /etc/default/gm-cockpit-autodeploy; set +a; /usr/local/sbin/gm-cockpit-autodeploy"
}

case "$STEP" in
  all) container; packages; tunnel; deploy_key; secrets; first_deploy ;;
  container|packages|tunnel|deploy_key|secrets|first_deploy) "$STEP" ;;
  *) echo "usage: $0 [all|container|packages|tunnel|deploy_key|secrets|first_deploy]"; exit 1 ;;
esac
say "done: https://$SITE_HOST"
