# Working on the cockpit

Notes for whoever (person or model) makes the next change. The user guide is `docs/guide.md`; it is also what the cockpit's help assistant knows, so update it whenever behaviour changes.

## Layout
- `pipeline/build.py`: extracted event data and company profiles → scored events, people and companies in SQLite. Re-runnable; decisions and settings versions are kept.
- `scoring.toml`: every weight, keyword and threshold. Each one is used by the scoring and editable in Criteria (main levers, then "All other settings"). A setting the page can't change shouldn't exist.
- `playbooks/`: the instructions the sourcing agents follow, versioned in the cockpit.
- `app/main.py` (API), `app/hubspot.py`, `app/copilot.py`, `app/summaries.py`; `app/static/index.html` is the whole interface.

## Run
```bash
uv run python pipeline/build.py
COCKPIT_ALLOW_OPEN=1 uv run uvicorn app.main:app --port 8765
```

## Working through feedback
1. `./deploy/feedback.sh` lists open notes, with what the person was looking at, their last actions and any errors.
2. Fix, test locally in a browser, commit, push to `main`, then `./deploy/deploy.sh` (builds, health-checks, rolls back on failure).
3. `./deploy/feedback.sh close <commit> <note id>...` marks the notes done with the commit.
4. `./deploy/publish.sh` updates the public copy (it removes every file that names people and refuses to publish if a name is left).

## Commits
Subject: what changed, in plain words. Body: at most one short line starting `Why:`, saying what Pierre wanted and the idea or logic behind it, in his voice ("I wanted ..."), with no technical detail. Purely technical fixes need no Why line.

## Rules
- Minimal and useful over complete. Remove what nobody acts on.
- A person decides: nothing is approved, sent or activated automatically.
- No em dashes in interface text or the assistant's replies.
- Never commit keys or access codes. People's data (`data/extracted/`, `data/briefs/`) stays out of the public copy.
