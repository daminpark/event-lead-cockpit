#!/usr/bin/env bash
# Feedback notes left with the cockpit's Feedback button (and by the copilot).
#   ./deploy/feedback.sh                        # open notes, oldest first
#   ./deploy/feedback.sh close <commit> <id>... # mark notes handled by a commit already pushed
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source deploy/local.env
mode=${1:-open}
if [[ $mode == close ]]; then
  commit=${2:-}
  [[ $# -ge 3 && $commit =~ ^[0-9a-f]{7,40}$ ]] && git merge-base --is-ancestor "$commit" origin/main 2>/dev/null \
    || { echo "Usage: ./deploy/feedback.sh close <commit on origin/main> <id>..." >&2; exit 2; }
  for id in "${@:3}"; do [[ $id =~ ^[0-9]+$ ]] || { echo "Not a note id: $id" >&2; exit 1; }; done
fi
ssh "$DEPLOY_HOST" "pct exec $DEPLOY_CT -- runuser -u gmcockpit -- python3 - $*" <<'PY'
import json, sqlite3, sys, datetime
con = sqlite3.connect("/var/lib/gm-cockpit/cockpit.db"); con.row_factory = sqlite3.Row
mode = sys.argv[1] if len(sys.argv) > 1 else "open"
if mode == "close":
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for i in sys.argv[3:]:
        con.execute("UPDATE feedback SET handled_at = ?, handled_note = ?, status = 'done' WHERE id = ? AND status IN ('open', 'planned')", (now, f"Fixed in {sys.argv[2]}", int(i)))
    con.commit(); print(f"closed {len(sys.argv) - 3}")
    sys.exit()
rows = con.execute("SELECT * FROM feedback WHERE status IN ('open', 'planned') ORDER BY id").fetchall()
print(f"{len(rows)} open notes")
for r in rows:
    print(f"\n[{r['id']}] {r['status']} · {r['created_at']} {r['author'] or '?'} on {r['view'] or '?'}\n  {r['comment']}")
    if r["target"]:
        t = json.loads(r["target"])
        print(f"  target: {t.get('selector')}  text: {(t.get('text') or '')[:150]!r}  row: {t.get('row')}")
    if r["context"]:
        c = json.loads(r["context"])
        st = c.get("state", {})
        print(f"  state:  view={st.get('view')} contact={st.get('contact')} scoring=v{st.get('scoring_version')} build={st.get('app_version')} {st.get('viewport')}")
        for t in c.get("trail", [])[-8:]:
            print(f"    {t['t']} {t['type']}: {t['detail']}")
errors = con.execute("SELECT id, source, message, path, created_at FROM errors WHERE resolved_at IS NULL ORDER BY id").fetchall()
if errors:
    print(f"\n{len(errors)} open errors (details under Insights > Errors)")
    for e in errors:
        print(f"  [{e['id']}] {e['created_at']} {e['source']} {e['path'] or ''}: {e['message'][:160]}")
PY
