"""The copilot: a chat that can look things up in the cockpit and propose changes.

It never changes what's live. Scoring and playbook changes are saved as new, inactive versions
that a person previews and activates in the Criteria or Playbooks tab.
"""

import datetime as dt
import json
import os
import time

import httpx

from pipeline import build as pipeline

API = "https://openrouter.ai/api/v1"
MAX_ROUNDS = 6
RATE = {"window": 3600, "max": 60, "calls": []}  # the link is public, so cap spend per hour

SYSTEM = """You are the help assistant inside the event lead cockpit. GeneralMind's team uses it to choose which events to attend \
and which people to meet there. (GeneralMind sells "Autopilot": AI that processes purchase orders, order confirmations and \
supplier invoices against the ERP.)

What you do:
1. Answer questions about what's in the cockpit: events (score, why, going or not), people (fit, brief, status: to review, \
approved, in HubSpot, rejected) and counts. Look everything up with your tools; never guess names, numbers or statuses.
2. Explain how the cockpit works, using the guide below.
3. Take people to the right page: put the links from your tool results in your answer as markdown links, \
e.g. [approved people at BME](#/event/bme-symposium-2026/approved).
4. Propose small changes to the scoring settings with propose_scoring_change. It saves an inactive version; tell the person \
to check it and click Activate.
5. Write down feedback about the cockpit with add_feedback_note.

What you don't do: approve, reject or unapprove people, mark events as going, send to HubSpot, edit playbooks, or search \
the web. If asked, say in one sentence where in the cockpit they can do it themselves, with a link.

Keep answers short: a sentence or a short list, with names and links. Plain language, no hype."""

STATUS_KEYS = {"to review": "review", "approved": "approved", "in HubSpot": "hubspot", "rejected": "rejected"}

TOOLS = [
    {"type": "function", "function": {
        "name": "find_people",
        "description": "Search people. Returns the best fits first with their status, brief and a link to their card.",
        "parameters": {"type": "object", "properties": {
            "event_id": {"type": "string", "description": "Only people at this event (ids come from list_events)"},
            "status": {"type": "string", "enum": list(STATUS_KEYS)},
            "suggestion": {"type": "string", "enum": ["strong fit", "possible", "low fit", "partner", "competitor", "customer"]},
            "text": {"type": "string", "description": "Matches name, title, company or talk"},
            "going_only": {"type": "boolean", "description": "Only events the team is going to"},
            "limit": {"type": "integer", "description": "Default 10, max 30"},
        }}}},
    {"type": "function", "function": {
        "name": "get_person",
        "description": "Everything about one person: every scoring reason, their talk, company details, source page and link.",
        "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "list_events",
        "description": "All events with id, dates, city, score, status (to decide, going, not going, already happened), counts and link.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_event",
        "description": "One event: why it scored as it did, why GeneralMind's buyers go, its sources, AI summary if written, counts by status and links.",
        "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "get_scoring",
        "description": "The active scoring settings (weights, keywords, thresholds) as JSON, for explaining scores or proposing a change.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "propose_scoring_change",
        "description": "Save a new INACTIVE scoring version with a few changes and return how many people would change lane. Paths are dot-separated, e.g. event.speaker_points or lanes.fast_track.",
        "parameters": {"type": "object", "properties": {
            "changes": {"type": "array", "items": {"type": "object", "properties": {"path": {"type": "string"}, "value": {}}, "required": ["path", "value"]}},
            "note": {"type": "string", "description": "What changes and why, one sentence"},
        }, "required": ["changes", "note"]}}},
    {"type": "function", "function": {
        "name": "add_feedback_note",
        "description": "Write down feedback about the cockpit for the team that builds it.",
        "parameters": {"type": "object", "properties": {"comment": {"type": "string"}}, "required": ["comment"]}}},
]

SUGGESTION = {"fast_track": "strong fit", "review": "possible", "filtered": "low fit", "partner": "partner", "competitor": "competitor", "customer": "customer"}


def key():
    from app import secrets_store
    return secrets_store.get("openrouter")


_models = {"at": 0, "list": []}


def models():
    """Tool-capable chat models on OpenRouter, cached for an hour."""
    if time.time() - _models["at"] < 3600 and _models["list"]:
        return _models["list"]
    r = httpx.get(f"{API}/models", timeout=20)
    r.raise_for_status()
    out = []
    for m in r.json().get("data", []):
        if "tools" not in (m.get("supported_parameters") or []):
            continue
        p = m.get("pricing") or {}
        out.append({"id": m["id"], "name": m.get("name", m["id"]),
                    "price": f"${float(p.get('prompt') or 0) * 1e6:.2f} / ${float(p.get('completion') or 0) * 1e6:.2f} per M tokens"})
    out.sort(key=lambda m: m["name"].lower())
    _models.update(at=time.time(), list=out)
    return out


def default_model():
    for m in models():
        if m["id"].startswith("anthropic/claude") and "sonnet" in m["id"]:
            return m["id"]
    return models()[0]["id"]


def setting(con, name, default=None):
    row = con.execute("SELECT value FROM settings WHERE key = ?", (name,)).fetchone()
    return row["value"] if row else default


class Tools:
    """What the assistant can look up or do. Reads the same data the page shows, including statuses."""

    def __init__(self, con, latest_decisions, validate_scoring, author):
        self.con, self.validate, self.author = con, validate_scoring, author
        self.decisions = latest_decisions(con)
        self.contacts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM contacts")]
        self.accounts = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM accounts")}
        self.events = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM events")}
        self.sent = {r["object_id"] for r in con.execute("SELECT object_id FROM hubspot_sync WHERE object_type = 'listing'")}
        self.actions = []

    def status(self, c):
        d = (self.decisions.get(("contact", c["id"])) or {}).get("decision")
        return "in HubSpot" if d == "approve" and c["id"] in self.sent else "approved" if d == "approve" else "rejected" if d == "reject" else "to review"

    def event_status(self, e):
        if e.get("past"):
            return "already happened"
        d = (self.decisions.get(("event", e["id"])) or {}).get("decision")
        return "going" if d == "approve" else "not going" if d == "reject" else "to decide"

    def person_link(self, c):
        return f"#/event/{c['event_id']}/{STATUS_KEYS[self.status(c)]}/{c['id']}"

    def compact(self, c):
        a = self.accounts.get(c["account_id"]) or {}
        return {"id": c["id"], "name": c["name"], "title": c.get("title"), "company": a.get("name") or c.get("company"),
                "event": self.events[c["event_id"]]["name"], "fit": c["score"], "suggestion": SUGGESTION[c["lane"]],
                "status": self.status(c), "brief": c.get("brief"), "link": self.person_link(c)}

    def find_people(self, event_id=None, status=None, suggestion=None, text=None, going_only=False, limit=10):
        limit = max(1, min(int(limit or 10), 30))
        t = (text or "").lower()
        going = {i for i, e in self.events.items() if self.event_status(e) == "going"}
        rows = []
        for c in self.contacts:
            a = self.accounts.get(c["account_id"]) or {}
            if event_id and c["event_id"] != event_id or going_only and c["event_id"] not in going:
                continue
            if status and self.status(c) != status or suggestion and SUGGESTION[c["lane"]] != suggestion:
                continue
            if t and t not in f"{c['name']} {c.get('title')} {a.get('name') or c.get('company')} {c.get('session')}".lower():
                continue
            rows.append(c)
        rows.sort(key=lambda c: -c["score"])
        return {"total": len(rows), "people": [self.compact(c) for c in rows[:limit]]}

    def get_person(self, id):
        c = next((c for c in self.contacts if c["id"] == id), None)
        if not c:
            return {"error": "No person with that id; use find_people first"}
        a = self.accounts.get(c["account_id"]) or {}
        p = a.get("profile") or {}
        return self.compact(c) | {"opener": c.get("opener"), "role_at_event": c.get("role_at_event"), "session": c.get("session"),
                                  "reasons": [f"{r['label']} (+{r['points']})" for r in c["reasons"]], "confidence": c["confidence"],
                                  "source_url": c.get("source_url"),
                                  "company_details": {k: p.get(k) for k in ("segment", "industry", "hq_country", "employees_band", "erp")}}

    def list_events(self):
        out = []
        for e in sorted(self.events.values(), key=lambda e: -e.get("score", 0)):
            out.append({"id": e["id"], "name": e["name"], "dates": f"{e['start']} to {e['end']}", "city": e.get("city"),
                        "score": e.get("score"), "status": self.event_status(e), "generalmind_has_a_stand": bool(e.get("generalmind_present")),
                        "strong_fit_people": e.get("counts", {}).get("strong"), "people": e.get("counts", {}).get("people"),
                        "link": f"#/event/{e['id']}"})
        return out

    def get_event(self, id):
        e = self.events.get(id)
        if not e:
            return {"error": "No event with that id; use list_events first"}
        summary = self.con.execute("SELECT text FROM event_summaries WHERE event_id = ?", (id,)).fetchone()
        counts = {}
        for c in self.contacts:
            if c["event_id"] == id:
                counts[self.status(c)] = counts.get(self.status(c), 0) + 1
        return {"id": id, "name": e["name"], "dates": f"{e['start']} to {e['end']}", "city": e.get("city"), "format": e.get("format"),
                "status": self.event_status(e), "score": e.get("score"), "score_reasons": [f"{r['label']} (+{r['points']})" for r in e.get("reasons", [])],
                "why": e.get("why"), "sources": e.get("sources"), "summary": summary["text"] if summary else None,
                "people_by_status": counts, "links": {"event": f"#/event/{id}", **{k: f"#/event/{id}/{v}" for k, v in STATUS_KEYS.items()}}}

    def get_scoring(self):
        row = self.con.execute("SELECT version, body FROM config_versions WHERE kind = 'scoring' AND active = 1").fetchone()
        return {"version": row["version"], "settings": json.loads(row["body"]), "link": "#/criteria"}

    def propose_scoring_change(self, changes, note):
        cfg = self.get_scoring()["settings"]
        for ch in changes:
            keys, node = ch["path"].split("."), cfg
            for k in keys[:-1]:
                if not isinstance(node, dict) or k not in node:
                    return {"error": f"Unknown setting {ch['path']}"}
                node = node[k]
            if keys[-1] not in node:
                return {"error": f"Unknown setting {ch['path']}"}
            node[keys[-1]] = ch["value"]
        errors = self.validate(cfg)
        if errors:
            return {"error": "; ".join(errors[:6])}
        _, contacts, _, _ = pipeline.compute(cfg, dt.date.today())
        now_lanes, new_lanes = {}, {}
        for c in self.contacts:
            now_lanes[SUGGESTION[c["lane"]]] = now_lanes.get(SUGGESTION[c["lane"]], 0) + 1
        for c in contacts:
            new_lanes[SUGGESTION[c["lane"]]] = new_lanes.get(SUGGESTION[c["lane"]], 0) + 1
        vid = pipeline.save_version(self.con, "scoring", json.dumps(cfg, ensure_ascii=False, indent=1), f"Assistant: {note}", self.author or "assistant", "ui")
        version = self.con.execute("SELECT version FROM config_versions WHERE id = ?", (vid,)).fetchone()["version"]
        self.con.commit()
        self.actions.append({"text": f"Saved scoring v{version} (not active): {note}", "version_id": vid, "kind": "scoring", "version": version})
        return {"saved_version": version, "active": False, "people_per_suggestion_now": now_lanes, "with_this_change": new_lanes, "link": "#/criteria"}

    def add_feedback_note(self, comment):
        self.con.execute("INSERT INTO feedback (comment, view, author, created_at) VALUES (?, 'assistant', ?, ?)",
                         (comment[:4000], self.author, pipeline.now()))
        self.con.commit()
        self.actions.append({"text": "Wrote a feedback note (Feedback tab)"})
        return {"ok": True, "link": "#/feedback"}


def chat(con, messages, context, latest_decisions, validate_scoring, author=None):
    if not key():
        raise RuntimeError("No OpenRouter key configured")
    now = time.time()
    RATE["calls"] = [t for t in RATE["calls"] if now - t < RATE["window"]]
    if len(RATE["calls"]) >= RATE["max"]:
        raise RuntimeError("The copilot has reached its hourly limit. Try again later.")
    RATE["calls"].append(now)

    model = setting(con, "copilot_model") or default_model()
    effort = setting(con, "copilot_effort") or "medium"  # thinking effort: the main lever on speed and cost
    tools = Tools(con, latest_decisions, validate_scoring, author)
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "guide.md"), encoding="utf-8") as f:
        guide = f.read()  # the same guide the page shows, so "how do I…" answers match the app
    convo = [{"role": "system", "content": SYSTEM + f"\n\n# The cockpit's guide\n{guide}\n\nToday is {dt.date.today().isoformat()}. The person is looking at: {json.dumps(context)[:600]}"}]
    convo += [{"role": m["role"], "content": m["content"]} for m in messages[-20:] if m.get("role") in ("user", "assistant")]
    with httpx.Client(timeout=httpx.Timeout(90.0)) as http:
        for _ in range(MAX_ROUNDS):
            r = http.post(f"{API}/chat/completions", headers={"Authorization": f"Bearer {key()}", "X-Title": "Event lead cockpit"},
                          json={"model": model, "messages": convo, "tools": TOOLS, "tool_choice": "auto", "max_tokens": 4000,
                                "reasoning": {"effort": effort}})
            if r.status_code >= 400:
                raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
            msg = r.json()["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            # keep reasoning fields: some models need them back on the next round
            convo.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls", "reasoning", "reasoning_details") and v is not None}
                         | {"content": msg.get("content") or ""})
            if not calls:
                return {"reply": msg.get("content") or "", "actions": tools.actions, "model": model, "effort": effort}
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    result = getattr(tools, name)(**args) if name in {t["function"]["name"] for t in TOOLS} else {"error": "unknown tool"}
                except Exception as e:  # a bad tool call goes back to the model, not to the user
                    result = {"error": str(e)[:300]}
                convo.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False, default=str)[:24000]})
    return {"reply": "I ran out of steps on that one. Could you narrow the question?", "actions": tools.actions, "model": model, "effort": effort}
