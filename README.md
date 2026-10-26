# Event lead cockpit

A case study for GeneralMind: which events to go to, who to meet there, and a review before HubSpot.

## Read more

- [The write-up](WRITEUP.md): what I built, and the plan for full lead generation.
- [How it evolved](EVOLUTION.md): the idea behind each step.
- [The live cockpit](https://leads.193vbr.com) (access code needed).

## The idea

- Event leads are for meeting people face to face, and time at the event is the limit.
- So choose the events first, then the people and companies worth meeting there.
- A person decides at every step. Nothing is approved or sent on its own.

## What it does

- **Events**: 10, from November 2026 to June 2027, scored on the best people we could meet, cost per meeting, timing and whether GeneralMind is a partner.
- **People and companies**: 680 people and 782 companies from public event pages, each scored with its reasons.
- **Meeting plan**: who to catch as they come off stage, and when.
- **No cold email**: in Germany it needs prior consent, so first contact happens at the event.
- **Review**: approve or reject each person. Undecided means no.
- **HubSpot**: approved people go across with their company, without overwriting what sales already has.
- **Playbooks**: the AI's steps and the scoring, in plain language and versioned.

## Privacy

- This public copy leaves out everything that names a person, in earlier versions too. The live cockpit has it, behind an access code.
- Only public business information is used: name, title, company and talk. No emails, phone numbers or LinkedIn.

## For developers

```bash
uv sync
uv run python pipeline/build.py
COCKPIT_ALLOW_OPEN=1 uv run uvicorn app.main:app --port 8765
```
