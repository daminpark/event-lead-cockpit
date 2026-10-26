"""The event scout: searches the web for upcoming events that fit the Events playbook, and writes AI summaries of events.

New finds land as candidates ("new"); a person tracks or dismisses them. Nothing the scout finds becomes an event on its own.
Run by the "Find new events" button, or daily by gm-cockpit-scout.timer when the owner has switched that on.

    python -m app.scout          # one daily run, if enabled in Settings
"""

import datetime as dt
import json
import re
import threading
import time

import httpx

from app import copilot
from pipeline import build as pipeline

API = "https://openrouter.ai/api/v1/chat/completions"
RUNS_PER_HOUR = 6
_lock = threading.Lock()

SCOUT_PROMPT = """You are the event scout for GeneralMind, a Berlin startup whose "Autopilot" processes purchase orders, order \
confirmations and supplier invoices arriving by email or PDF and posts them into SAP, Oracle, Dynamics or JD Edwards.

Follow this playbook:
{playbook}

Today is {today}. Search the web for upcoming events (from {today} to about 9 months ahead) that fit the playbook and are \
NOT already known. Known events and earlier finds (don't return these, or other editions of them):
{known}

Return up to {limit} new events. Check each date on the organiser's own site. Prefer events whose speaker, agenda, exhibitor \
or participant lists are public, and say where. Answer with ONLY a JSON array, no prose, in this shape:
[{{"name": "...", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "city": "...", "country": "ISO2", "venue": "... or null",
  "format": "Congress | Trade fair | Summit | User group", "language": "...", "url": "official event URL",
  "why": "one or two plain sentences on why GeneralMind's buyers are there",
  "personas": ["procurement" | "supply_chain" | "logistics" | "order_management" | "finance_ap" | "operations"],
  "sources": [{{"type": "speakers | agenda | exhibitors | participants", "edition": "e.g. 2027 or 2026 (previous)", "url": "..."}}],
  "date_confirmed": true | false, "notes": "anything a reviewer should know, or null"}}]"""

SUMMARY_PROMPT = """Write a short briefing for a GeneralMind team member deciding whether to attend this event and who to meet there. \
GeneralMind sells "Autopilot": AI that processes purchase orders, order confirmations and supplier invoices against the ERP. \
Use ONLY the facts below; don't invent numbers, names or claims. Plain, modest language, no hype, no em dashes.

Format, in markdown, about 120 words in total:
**Why go:** two sentences.
**Who to meet:** two or three named people from the list, each with a short reason.
**Watch out:** one sentence on the main caveat (timing, last year's list, vendor-heavy, travel, no named people yet...).

Facts:
{facts}"""


def _chat(con, messages, web=False, max_tokens=4000):
    key = copilot.key()
    if not key:
        raise RuntimeError("No OpenRouter key configured (Settings)")
    model = copilot.setting(con, "copilot_model") or copilot.default_model()
    effort = copilot.setting(con, "copilot_effort") or "medium"
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "reasoning": {"effort": effort}}
    if web:
        body["plugins"] = [{"id": "web", "max_results": 10}]
    r = httpx.post(API, headers={"Authorization": f"Bearer {key}", "X-Title": "Event lead cockpit"}, json=body, timeout=300)
    if r.status_code >= 400:
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
    d = r.json()
    return d["choices"][0]["message"].get("content") or "", model, (d.get("usage") or {}).get("cost")


def _json_array(text):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise ValueError("The scout's answer had no JSON list")
    return json.loads(m.group(0))


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _slug(name, start):
    return re.sub(r"[^a-z0-9]+", "-", f"{name} {start[:4]}".lower()).strip("-")[:80]


def recent_runs(con):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat(timespec="seconds")
    return con.execute("SELECT COUNT(*) FROM scout_runs WHERE started_at > ?", (since,)).fetchone()[0]


def run(trigger="button", limit=8):
    """One scout run. Returns the run id; results go to event_candidates. Safe to call from a thread."""
    if not _lock.acquire(blocking=False):
        raise RuntimeError("The scout is already running")
    con = pipeline.connect(pipeline.DB)
    try:
        if recent_runs(con) >= RUNS_PER_HOUR:
            raise RuntimeError("The scout has run enough this hour. Try again later.")
        cur = con.execute("INSERT INTO scout_runs (trigger, started_at, status) VALUES (?, ?, 'running')", (trigger, pipeline.now()))
        run_id = cur.lastrowid
        con.commit()
        try:
            playbook = con.execute("SELECT body FROM config_versions WHERE kind = 'playbook:events' AND active = 1").fetchone()["body"]
            known = [json.loads(r["data"]) for r in con.execute("SELECT data FROM events")]
            seen = [json.loads(r["data"]) for r in con.execute("SELECT data FROM event_candidates")]
            known_lines = "\n".join(f"- {e['name']} ({e.get('start', '?')}, {e.get('city', '?')}) {e.get('url', '')}" for e in known + seen)
            text, model, cost = _chat(con, [{"role": "user", "content": SCOUT_PROMPT.format(
                playbook=playbook, today=dt.date.today().isoformat(), known=known_lines, limit=limit)}], web=True)
            found = _json_array(text)
            known_keys = {_norm(e["name"]) for e in known + seen} | {_norm(e.get("url")) for e in known + seen if e.get("url")}
            today = dt.date.today().isoformat()
            added = 0
            for e in found:
                if not isinstance(e, dict) or not e.get("name") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e.get("start", ""))):
                    continue
                if e["start"] < today or _norm(e["name"]) in known_keys or _norm(e.get("url")) in known_keys:
                    continue
                e["end"] = e.get("end") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e.get("end", ""))) else e["start"]
                e["id"] = _slug(e["name"], e["start"])
                e["sources"] = [s for s in (e.get("sources") or []) if isinstance(s, dict) and str(s.get("url", "")).startswith("http")]
                con.execute("INSERT OR IGNORE INTO event_candidates (id, run_id, found_at, status, data) VALUES (?, ?, ?, 'new', ?)",
                            (e["id"], run_id, pipeline.now(), json.dumps(e, ensure_ascii=False)))
                known_keys.add(_norm(e["name"]))
                added += 1
            con.execute("UPDATE scout_runs SET finished_at = ?, status = 'done', found = ?, model = ?, cost = ? WHERE id = ?",
                        (pipeline.now(), added, model, cost, run_id))
            con.execute("INSERT INTO events_log (kind, message, created_at) VALUES ('scout', ?, ?)",
                        (f"Event scout ({trigger}) found {added} new event{'s' if added != 1 else ''}", pipeline.now()))
        except Exception as e:
            con.execute("UPDATE scout_runs SET finished_at = ?, status = 'failed', error = ? WHERE id = ?", (pipeline.now(), str(e)[:500], run_id))
            con.execute("INSERT INTO events_log (kind, message, created_at) VALUES ('scout', ?, ?)",
                        (f"Event scout ({trigger}) failed: {str(e)[:200]}", pipeline.now()))
        con.commit()
        return run_id
    finally:
        con.close()
        _lock.release()


def start(trigger="button"):
    """Start a run in the background so the page doesn't wait (and Cloudflare doesn't time out)."""
    if _lock.locked():
        raise RuntimeError("The scout is already running")
    with pipeline.connect(pipeline.DB) as con:
        if recent_runs(con) >= RUNS_PER_HOUR:
            raise RuntimeError("The scout has run enough this hour. Try again later.")
    threading.Thread(target=run, args=(trigger,), daemon=True).start()
    time.sleep(0.3)  # let the run row appear before the page polls


def summarize(con, event_id):
    """An AI briefing for one event, from the cockpit's own data. Cached until regenerated."""
    row = con.execute("SELECT data FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        raise RuntimeError("Unknown event")
    e = json.loads(row["data"])
    people = [json.loads(r["data"]) for r in con.execute(
        "SELECT data FROM contacts WHERE event_id = ? AND lane = 'fast_track' ORDER BY score DESC LIMIT 12", (event_id,))]
    accounts = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM accounts")}
    facts = {
        "event": {k: e.get(k) for k in ("name", "start", "end", "city", "country", "format", "language", "why", "generalmind_present", "date_note")},
        "score": e.get("score"), "score_reasons": [f"{r['label']} (+{r['points']})" for r in e.get("reasons", [])],
        "counts": e.get("counts"), "list_editions": [s.get("edition") for s in e.get("sources", [])],
        "people_not_sourced_yet": bool(e.get("not_sourced")),
        "top_people": [{"name": c["name"], "title": c.get("title"), "company": (accounts.get(c["account_id"]) or {}).get("name") or c.get("company"),
                        "session": c.get("session"), "fit": c["score"]} for c in people],
    }
    text, model, _ = _chat(con, [{"role": "user", "content": SUMMARY_PROMPT.format(facts=json.dumps(facts, ensure_ascii=False, indent=1))}], max_tokens=2500)
    text = text.strip()
    con.execute("INSERT OR REPLACE INTO event_summaries VALUES (?, ?, ?, ?)", (event_id, text, model, pipeline.now()))
    con.commit()
    return {"text": text, "model": model}


if __name__ == "__main__":  # the daily timer
    with pipeline.connect(pipeline.DB) as c:
        enabled = c.execute("SELECT value FROM settings WHERE key = 'scout_daily'").fetchone()
    if enabled and enabled["value"] == "1":
        print("scout run", run("daily"))
    else:
        print("daily scout is off (Settings)")
