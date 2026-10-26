"""AI summaries of events: a short briefing (why go, who to meet, the main caveat) written from the cockpit's own data."""

import json

import httpx

from app import copilot
from pipeline import build as pipeline

API = "https://openrouter.ai/api/v1/chat/completions"

SUMMARY_PROMPT = """Write a short briefing for a GeneralMind team member deciding whether to attend this event and who to meet there. \
GeneralMind sells "Autopilot": AI that processes purchase orders, order confirmations and supplier invoices against the ERP. \
Use ONLY the facts below; don't invent numbers, names or claims. Plain, modest language, no hype, no em dashes.

Format, in markdown, about 120 words in total:
**Why go:** two sentences.
**Who to meet:** two or three named people from the list, each with a short reason.
**Watch out:** one sentence on the main caveat (timing, last year's list, vendor-heavy, travel, no named people yet...).

Facts:
{facts}"""


def _chat(con, messages, max_tokens=4000):
    key = copilot.key()
    if not key:
        raise RuntimeError("No OpenRouter key configured (Settings)")
    model = copilot.setting(con, "copilot_model") or copilot.default_model()
    effort = copilot.setting(con, "copilot_effort") or "medium"
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "reasoning": {"effort": effort}}
    r = httpx.post(API, headers={"Authorization": f"Bearer {key}", "X-Title": "Event lead cockpit"}, json=body, timeout=300)
    if r.status_code >= 400:
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
    d = r.json()
    return d["choices"][0]["message"].get("content") or "", model, (d.get("usage") or {}).get("cost")


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
