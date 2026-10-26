#!/usr/bin/env bash
# Refresh the public copy (github.com/daminpark/event-lead-cockpit): the same commits and dates, minus the files
# that name people, and with any name that slipped into another file replaced. Commits made before the "Why:"
# convention get their why line from deploy/commit-notes.json (written afterwards from the build conversation).
# Refuses to publish if any person's name is still found anywhere in the history.
#   ./deploy/publish.sh            # build, check and push
#   ./deploy/publish.sh --dry-run  # build and check only, and print the public history
set -euo pipefail
cd "$(dirname "$0")/.."
NOTES="$PWD/deploy/commit-notes.json"
PUBLIC="${PUBLIC_REPO:-https://github.com/daminpark/event-lead-cockpit.git}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# every person named in the private data (kept only in this temporary folder)
python3 - "$tmp" <<'PY'
import glob, json, sys
names = set()
for p in glob.glob("data/extracted/*.json"):
    for x in json.load(open(p, encoding="utf-8")).get("people", []):
        n = (x.get("name") or "").strip()
        if len(n) > 4:
            names.add(n)
with open(f"{sys.argv[1]}/names.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(names)))
with open(f"{sys.argv[1]}/replace.txt", "w", encoding="utf-8") as f:
    for n in sorted(names, key=len, reverse=True):
        f.write(f"literal:{n}==>[name removed]\n")
print(f"{len(names)} names to keep out")
PY
git clone --quiet --no-local . "$tmp/repo"
cd "$tmp/repo"
NOTES="$NOTES" uvx --quiet git-filter-repo --quiet --force --invert-paths \
  --path data/extracted --path data/briefs --path data/source_checks.json \
  --commit-callback '
import json, os
why = json.load(open(os.environ["NOTES"], encoding="utf-8")).get(commit.original_id.decode())
if why:
    subject, _, rest = commit.message.decode().partition("\n")
    commit.message = (subject + "\n\n" + why + "\n" + ("\n" + rest.lstrip("\n") if rest.strip() else "")).encode()
'
uvx --quiet git-filter-repo --quiet --force --replace-text "$tmp/replace.txt"
python3 - "$tmp/names.txt" <<'PY'
import subprocess, sys
names = [n for n in open(sys.argv[1], encoding="utf-8").read().splitlines() if n]
history = subprocess.run(["git", "log", "-p", "--all", "--format=%B"], capture_output=True, text=True).stdout
left = [n for n in names if n in history]
files = subprocess.run(["git", "log", "--all", "--name-only", "--format="], capture_output=True, text=True).stdout
if left or "data/extracted/" in files or "data/briefs/" in files or "source_checks" in files:
    sys.exit(f"Not publishing: people data still in the history ({len(left)} names)")
print(f"checked: no names left in {subprocess.run(['git', 'rev-list', '--count', 'HEAD'], capture_output=True, text=True).stdout.strip()} commits")
PY
[ "${1:-}" = "--dry-run" ] && { git log --reverse --date=format:%H:%M --format="%h  %ad  %B" | grep -v "^Co-Authored-By"; echo "dry run: not pushed"; exit 0; }
git remote add public "$PUBLIC"
git push --quiet --force public HEAD:main
echo "public copy updated: ${PUBLIC%.git}"
