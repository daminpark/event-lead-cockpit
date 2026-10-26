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

SYSTEM = """You are the copilot inside an event lead cockpit built for GeneralMind, a Berlin startup whose "Autopilot" \
processes purchase orders, order confirmations and supplier invoices arriving by email or PDF and posts them into SAP, \
Oracle, Dynamics or JD Edwards. The cockpit sources people and companies from 10 upcoming events, scores them with \
transparent rules (versioned settings), and a person approves or rejects each lead before it goes to HubSpot.

You help the team: answer questions about the leads, events, scoring and playbooks using your tools; explain why a lead \
scored as it did; suggest who to meet first; and propose changes to scoring weights, keywords or playbooks.

Rules:
- Look things up with tools before answering questions about data. Never invent leads, numbers or facts.
- You cannot change what's live. To change scoring or a playbook, call a propose_* tool: it saves a new inactive version \
and returns its preview. Then tell the person which version to review and activate in the Criteria or Playbooks tab.
- If someone gives feedback about the app itself, file it with add_feedback_note.
- Keep answers short and concrete. Use names. Plain language, no hype.
- Legal: business information from public pages only; no emails or phone numbers are collected; respect the \
do-not-contact list. In Germany cold email needs prior consent (UWG §7), so favour meetings at events and introductions."""

TOOLS = [
    {"type": "function", "function": {
        "name": "query_leads",
        "description": "Search contacts (people) or accounts (companies). Returns the top matches by fit score, with lane, reasons and decisions.",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["contacts", "accounts"]},
            "text": {"type": "string", "description": "Matches name, title, company, session or industry"},
            "event_id": {"type": "string"}, "lane": {"type": "string", "enum": ["fast_track", "review", "filtered", "partner", "competitor", "customer"]},
            "industry": {"type": "string"}, "min_score": {"type": "integer"},
            "decision": {"type": "string", "enum": ["approve", "reject", "none"]},
            "limit": {"type": "integer", "description": "Default 15, max 40"},
        }, "required": ["kind"]}}},
    {"type": "function", "function": {
        "name": "get_lead",
        "description": "Full detail for one contact or account by id, including every scoring reason and the source page.",
        "parameters": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["contact", "account"]}, "id": {"type": "string"}}, "required": ["kind", "id"]}}},
    {"type": "function", "function": {
        "name": "get_stats",
        "description": "Counts by lane, by event and by industry; review decisions and agreement with the scoring; HubSpot sync counts.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_events",
        "description": "The events with dates, city, why they matter and their source pages.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_config",
        "description": "The active scoring settings (JSON) or a playbook (text).",
        "parameters": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["scoring", "playbook:events", "playbook:sourcing", "playbook:profiling"]}}, "required": ["kind"]}}},
    {"type": "function", "function": {
        "name": "propose_scoring_change",
        "description": "Save a new INACTIVE scoring version with the given changes and return how lanes would shift. Paths are dot-separated, e.g. role.functions.procurement.points or company.core_industries.",
        "parameters": {"type": "object", "properties": {
            "changes": {"type": "array", "items": {"type": "object", "properties": {"path": {"type": "string"}, "value": {}}, "required": ["path", "value"]}},
            "note": {"type": "string", "description": "What changes and why, one sentence"},
        }, "required": ["changes", "note"]}}},
    {"type": "function", "function": {
        "name": "propose_playbook_change",
        "description": "Save a new INACTIVE version of a playbook with the full new text.",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["playbook:events", "playbook:sourcing", "playbook:profiling"]},
            "text": {"type": "string"}, "note": {"type": "string"},
        }, "required": ["kind", "text", "note"]}}},
    {"type": "function", "function": {
        "name": "add_feedback_note",
        "description": "File a feedback note about the app for the developer.",
        "parameters": {"type": "object", "properties": {"comment": {"type": "string"}}, "required": ["comment"]}}},
]


def key():
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


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


def compact_contact(c, accounts, decisions):
    a = accounts.get(c["account_id"]) or {}
    d = decisions.get(("contact", c["id"]))
    return {"id": c["id"], "name": c["name"], "title": c.get("title"), "company": a.get("name") or c.get("company"),
            "industry": (a.get("profile") or {}).get("industry"), "event": c["event_id"], "role": c.get("role_at_event"),
            "session": c.get("session"), "score": c["score"], "lane": c["lane"], "decision": d["decision"] if d else None,
            "top_reasons": [f"{r['label']} +{r['points']}" for r in sorted(c["reasons"], key=lambda r: -r["points"])[:4] if r["points"]],
            "brief": c.get("brief")}


def compact_account(a, decisions):
    p = a.get("profile") or {}
    d = decisions.get(("account", a["id"]))
    return {"id": a["id"], "name": a["name"], "industry": p.get("industry"), "country": p.get("hq_country"),
            "size": p.get("employees_band"), "segment": p.get("segment"), "events": a["events"], "contacts": len(a["contact_ids"]),
            "score": a["score"], "lane": a["lane"], "decision": d["decision"] if d else None}


class Tools:
    def __init__(self, con, latest_decisions, validate_scoring, author):
        self.con, self.validate, self.author = con, validate_scoring, author
        self.decisions = latest_decisions(con)
        self.contacts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM contacts")]
        self.accounts = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM accounts")}
        self.actions = []

    def query_leads(self, kind, text=None, event_id=None, lane=None, industry=None, min_score=None, decision=None, limit=15):
        limit = max(1, min(int(limit or 15), 40))
        t = (text or "").lower()
        dec = lambda k, i: (self.decisions.get((k, i)) or {}).get("decision") or "none"
        if kind == "accounts":
            rows = [a for a in self.accounts.values()
                    if (not t or t in f"{a['name']} {(a.get('profile') or {}).get('industry')}".lower())
                    and (not event_id or event_id in a["events"]) and (not lane or a["lane"] == lane)
                    and (not industry or industry.lower() in ((a.get("profile") or {}).get("industry") or "").lower())
                    and (min_score is None or a["score"] >= min_score) and (not decision or dec("account", a["id"]) == decision)]
            rows.sort(key=lambda a: -a["score"])
            return {"total": len(rows), "rows": [compact_account(a, self.decisions) for a in rows[:limit]]}
        rows = []
        for c in self.contacts:
            a = self.accounts.get(c["account_id"]) or {}
            hay = f"{c['name']} {c.get('title')} {a.get('name') or c.get('company')} {c.get('session')} {(a.get('profile') or {}).get('industry')}".lower()
            if (t and t not in hay) or (event_id and c["event_id"] != event_id) or (lane and c["lane"] != lane):
                continue
            if industry and industry.lower() not in ((a.get("profile") or {}).get("industry") or "").lower():
                continue
            if (min_score is not None and c["score"] < min_score) or (decision and dec("contact", c["id"]) != decision):
                continue
            rows.append(c)
        rows.sort(key=lambda c: -c["score"])
        return {"total": len(rows), "rows": [compact_contact(c, self.accounts, self.decisions) for c in rows[:limit]]}

    def get_lead(self, kind, id):
        if kind == "account":
            a = self.accounts.get(id)
            return a or {"error": "not found"}
        c = next((c for c in self.contacts if c["id"] == id), None)
        if not c:
            return {"error": "not found"}
        return c | {"company_profile": (self.accounts.get(c["account_id"]) or {}).get("profile")}

    def get_stats(self):
        lanes, by_event, by_industry = {}, {}, {}
        for c in self.contacts:
            lanes[c["lane"]] = lanes.get(c["lane"], 0) + 1
            e = by_event.setdefault(c["event_id"], {"contacts": 0, "fast_track": 0, "approved": 0})
            e["contacts"] += 1
            e["fast_track"] += c["lane"] == "fast_track"
            ind = (self.accounts.get(c["account_id"]) or {}).get("profile", {}).get("industry") or "Unknown"
            by_industry[ind] = by_industry.get(ind, 0) + (c["lane"] == "fast_track")
        decided = {"approve": 0, "reject": 0}
        reasons = {}
        for (k, _), d in self.decisions.items():
            decided[d["decision"]] = decided.get(d["decision"], 0) + 1
            if d["decision"] == "reject":
                reasons[d.get("reason") or "none"] = reasons.get(d.get("reason") or "none", 0) + 1
        for (k, i), d in self.decisions.items():
            if k == "contact" and d["decision"] == "approve":
                c = next((c for c in self.contacts if c["id"] == i), None)
                if c:
                    by_event.setdefault(c["event_id"], {"contacts": 0, "fast_track": 0, "approved": 0})["approved"] += 1
        synced = {r["object_type"]: r["n"] for r in self.con.execute("SELECT object_type, COUNT(*) n FROM hubspot_sync GROUP BY object_type")}
        return {"contact_lanes": lanes, "by_event": by_event, "fast_track_by_industry": dict(sorted(by_industry.items(), key=lambda x: -x[1])[:12]),
                "decisions": decided, "reject_reasons": reasons, "hubspot": synced, "accounts": len(self.accounts)}

    def get_events(self):
        return [json.loads(r["data"]) for r in self.con.execute("SELECT data FROM events")]

    def get_config(self, kind):
        row = self.con.execute("SELECT version, body FROM config_versions WHERE kind = ? AND active = 1", (kind,)).fetchone()
        return {"version": row["version"], "body": row["body"]}

    def propose_scoring_change(self, changes, note):
        cfg = json.loads(self.get_config("scoring")["body"])
        for ch in changes:
            keys = ch["path"].split(".")
            node = cfg
            for k in keys[:-1]:
                if not isinstance(node, dict) or k not in node:
                    return {"error": f"Unknown path {ch['path']}"}
                node = node[k]
            if keys[-1] not in node:
                return {"error": f"Unknown path {ch['path']}"}
            node[keys[-1]] = ch["value"]
        errors = self.validate(cfg)
        if errors:
            return {"error": "; ".join(errors[:6])}
        _, contacts, _, _ = pipeline.compute(cfg, dt.date.today())
        before, after = {}, {}
        for c in self.contacts:
            before[c["lane"]] = before.get(c["lane"], 0) + 1
        for c in contacts:
            after[c["lane"]] = after.get(c["lane"], 0) + 1
        vid = pipeline.save_version(self.con, "scoring", json.dumps(cfg, ensure_ascii=False, indent=1), f"Copilot: {note}", self.author or "copilot", "ui")
        version = self.con.execute("SELECT version FROM config_versions WHERE id = ?", (vid,)).fetchone()["version"]
        self.con.commit()
        self.actions.append(f"Saved scoring v{version} (not active): {note}")
        return {"saved_version": version, "active": False, "lanes_now": before, "lanes_with_change": after}

    def propose_playbook_change(self, kind, text, note):
        vid = pipeline.save_version(self.con, kind, text, f"Copilot: {note}", self.author or "copilot", "ui")
        version = self.con.execute("SELECT version FROM config_versions WHERE id = ?", (vid,)).fetchone()["version"]
        self.con.commit()
        self.actions.append(f"Saved {kind.split(':')[1]} playbook v{version} (not active): {note}")
        return {"saved_version": version, "active": False}

    def add_feedback_note(self, comment):
        self.con.execute("INSERT INTO feedback (comment, view, author, created_at) VALUES (?, 'copilot', ?, ?)",
                         (comment[:4000], self.author, pipeline.now()))
        self.con.commit()
        self.actions.append("Filed a feedback note")
        return {"ok": True}


def chat(con, messages, context, latest_decisions, validate_scoring, author=None):
    if not key():
        raise RuntimeError("No OpenRouter key configured")
    now = time.time()
    RATE["calls"] = [t for t in RATE["calls"] if now - t < RATE["window"]]
    if len(RATE["calls"]) >= RATE["max"]:
        raise RuntimeError("The copilot has reached its hourly limit. Try again later.")
    RATE["calls"].append(now)

    model = setting(con, "copilot_model") or default_model()
    tools = Tools(con, latest_decisions, validate_scoring, author)
    convo = [{"role": "system", "content": SYSTEM + f"\n\nToday is {dt.date.today().isoformat()}. The person is looking at: {json.dumps(context)[:600]}"}]
    convo += [{"role": m["role"], "content": m["content"]} for m in messages[-20:] if m.get("role") in ("user", "assistant")]
    with httpx.Client(timeout=httpx.Timeout(90.0)) as http:
        for _ in range(MAX_ROUNDS):
            r = http.post(f"{API}/chat/completions", headers={"Authorization": f"Bearer {key()}", "X-Title": "Event lead cockpit"},
                          json={"model": model, "messages": convo, "tools": TOOLS, "tool_choice": "auto", "max_tokens": 1500})
            if r.status_code >= 400:
                raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
            msg = r.json()["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            # keep reasoning fields: some models need them back on the next round
            convo.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls", "reasoning", "reasoning_details") and v is not None}
                         | {"content": msg.get("content") or ""})
            if not calls:
                return {"reply": msg.get("content") or "", "actions": tools.actions, "model": model}
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    result = getattr(tools, name)(**args) if name in {t["function"]["name"] for t in TOOLS} else {"error": "unknown tool"}
                except Exception as e:  # a bad tool call goes back to the model, not to the user
                    result = {"error": str(e)[:300]}
                convo.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False, default=str)[:24000]})
    return {"reply": "I ran out of steps on that one. Could you narrow the question?", "actions": tools.actions, "model": model}
