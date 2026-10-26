# Event lead cockpit

A case study for GeneralMind (Growth Associate, CEO Office), built on 26 October 2026: find upcoming events where GeneralMind's buyers go, source the people and companies named on their public pages, and review them in a cockpit before they go to HubSpot.

The task: *"Find 10 relevant upcoming events for GeneralMind and set up a system that sources leads attending these events into a cockpit/interface for review. Then conceptualize how you would expand this into a full lead generation system, where leads are sourced into the interface based on defined criteria, reviewed, and pushed to HubSpot."*

- **Write-up** (what I built and how I'd grow it): [WRITEUP.md](WRITEUP.md)
- **Live cockpit**: https://leads.193vbr.com (behind an access code)
- **How it evolved**: [EVOLUTION.md](EVOLUTION.md), the ideas behind each step. Commits that carry an idea have a one-line "Why"; for the earlier ones it was added afterwards from the build conversation.

## What it does

1. **Events.** Ten events (procurement and supply-chain congresses, trade fairs where the exhibitors are the prospects, a shared-services week), each judged on the best people we could actually meet there (the average fit of the best N, where N is the meetings possible), then whether GeneralMind has a stand, timing, travel time from Berlin and whether this year's list is out. Each event has an AI summary, its score broken down, and a meeting plan (people sent × days × meetings a day, so how many to invite). You mark events Going or Not going.
2. **People.** About 700 people named on the events' speaker, agenda and partner pages, each with a fit score and its reasons, a five-second brief and an opener for the event. Everyone starts in *To review*; a person approves or rejects. Nothing is approved automatically.
3. **HubSpot.** Approved people are sent with their companies, linked and deduplicated by the cockpit's own ids, with the fit score, reasons, source event and source page as properties. Or downloaded per event as a CSV.

Around that: scoring settings and playbooks that are versioned (preview a change against past decisions before activating it), a playbook editor with a line diff and a model that discusses and edits the draft, a help assistant that answers from the cockpit's data and links to the right page, a feedback button that records what the person was doing, error logging, owner and team roles, and a do-not-contact list.

## How it's built

- `pipeline/build.py`: turns the extracted event data and company profiles into scored events, people and companies (SQLite). Re-runnable; reviewer decisions and settings versions are kept.
- `scoring.toml`: every weight, keyword and threshold, in one readable file. Editable in the cockpit, where each save is a version.
- `playbooks/`: the plain-language instructions the AI agents follow to find events, source people and profile companies.
- `app/main.py`: FastAPI app. `app/hubspot.py` (push and removal), `app/copilot.py` (help assistant and playbook chat via OpenRouter), `app/summaries.py` (event summaries).
- `app/static/index.html`: the whole interface, one page of vanilla JavaScript.
- `deploy/`: a Proxmox container behind a Cloudflare Tunnel, deployed automatically from `main` with a health check and rollback.

The sourcing itself (fetching the event pages, extracting people, checking every name against the saved page, profiling companies, writing the briefs) was run by AI agents in a harness, each step checked by a second agent. Making that a standalone, scheduled agent is part of the plan in the write-up.

## Data and privacy

This public copy leaves out the files that name people: the extracted speaker lists (`data/extracted/`), the briefs (`data/briefs/`) and the source checks. They were removed from every commit, so the history shows how the code evolved without republishing anyone's details. The event list and the company profiles are included. The live cockpit uses the full data behind an access code.

Only business information from public event pages is used (name, title, company, talk). No emails or phone numbers are collected, LinkedIn isn't used, and sites that block automated access are respected.

## Running it locally

```bash
uv sync
uv run python pipeline/build.py
COCKPIT_ALLOW_OPEN=1 uv run uvicorn app.main:app --port 8765
```

Without the people data (left out of this copy) the cockpit shows the events, but no people or companies.
