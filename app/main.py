"""The review cockpit: serves the page, records decisions, versions settings, exports and pushes to HubSpot."""

import csv
import datetime as dt
import hmac
import io
import json
import os
import re
import threading
from contextlib import closing
from typing import Literal

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import copilot, hubspot
from pipeline import build as pipeline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "app", "static")
VERSION = open(os.path.join(ROOT, "VERSION")).read().strip()[:7] if os.path.exists(os.path.join(ROOT, "VERSION")) else "dev"

app = FastAPI(title="Event lead cockpit", docs_url=None, redoc_url=None)
write_lock = threading.Lock()  # one writer at a time for rebuilds and pushes

# The leads are real people, and the page can push to HubSpot and spend on the copilot,
# so everything sits behind a shared access code (sent with the link).
CODE = os.environ.get("COCKPIT_CODE", "").strip()
OPEN = os.environ.get("COCKPIT_ALLOW_OPEN") == "1"  # local development only
if not CODE and not OPEN:
    raise RuntimeError("Set COCKPIT_CODE (or COCKPIT_ALLOW_OPEN=1 for local development)")
OPEN_PATHS = {"/healthz", "/login"}

LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Event Lead Cockpit</title><style>
:root{--bg:#f6f6f4;--panel:#fff;--ink:#1b1c1f;--muted:#6a6e76;--line:#e5e5e1;--accent:#2f4fd8}
@media (prefers-color-scheme:dark){:root{--bg:#131416;--panel:#1b1c1f;--ink:#ececee;--muted:#a0a4ab;--line:#2c2e33;--accent:#7d95ff}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
form{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:28px;width:min(360px,calc(100vw - 32px))}
h1{font-size:18px;margin:0 0 4px}p{color:var(--muted);margin:0 0 18px;font-size:14px}
input{width:100%;box-sizing:border-box;font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:9px;background:var(--bg);color:var(--ink);margin-bottom:12px}
button{width:100%;font:inherit;font-weight:600;padding:10px;border:0;border-radius:9px;background:var(--accent);color:#fff;cursor:pointer}
.err{color:#bf2f2f;font-size:13px;margin:-4px 0 12px}</style></head><body>
<form method="post" action="login"><h1>Event Lead Cockpit</h1><p>Case study for GeneralMind. Please enter the access code from the email.</p>
ERROR<input name="code" type="password" autocomplete="current-password" autofocus placeholder="Access code"><button>Open</button></form></body></html>"""


def code_ok(value):
    if not CODE:
        return OPEN
    return value is not None and hmac.compare_digest(value.encode(), CODE.encode())


@app.middleware("http")
async def require_code(request: Request, call_next):
    if request.url.path in OPEN_PATHS or code_ok(request.cookies.get("gm_code")):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Access code needed"}, status_code=401)
    return HTMLResponse(LOGIN_PAGE.replace("ERROR", ""), status_code=401)


@app.post("/login")
def login(code: str = Form(max_length=200)):
    if not code_ok(code.strip()):
        threading.Event().wait(1.5)  # slow down guessing
        return HTMLResponse(LOGIN_PAGE.replace("ERROR", '<div class="err">That code didn\'t work.</div>'), status_code=401)
    resp = RedirectResponse("./", status_code=303)
    resp.set_cookie("gm_code", code.strip(), max_age=60 * 60 * 24 * 30, httponly=True, secure=True, samesite="lax")
    return resp


def db():
    return closing(pipeline.connect(pipeline.DB))


def log(con, kind, message, data=None):
    con.execute("INSERT INTO events_log (kind, message, data, created_at) VALUES (?, ?, ?, ?)",
                (kind, message, json.dumps(data, ensure_ascii=False) if data is not None else None, pipeline.now()))


def latest_decisions(con):
    rows = con.execute(
        "SELECT * FROM decisions WHERE id IN (SELECT MAX(id) FROM decisions GROUP BY object_type, object_id)"
    ).fetchall()
    return {(r["object_type"], r["object_id"]): dict(r) for r in rows if r["decision"] != "clear"}


@app.on_event("startup")
def ensure_built():
    with db() as con:
        if not con.execute("SELECT name FROM sqlite_master WHERE name = 'contacts'").fetchone():
            pipeline.build(con=con)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": VERSION}


def rebuild_if_stale(con):
    meta = con.execute("SELECT value FROM meta WHERE key = 'today'").fetchone()
    if meta and json.loads(meta["value"]) != dt.date.today().isoformat() and write_lock.acquire(blocking=False):
        try:
            pipeline.build(con=con)
        finally:
            write_lock.release()


@app.get("/api/data")
def data():
    with db() as con:
        rebuild_if_stale(con)
        rows = lambda sql: [json.loads(r["data"]) for r in con.execute(sql)]
        return {
            "events": rows("SELECT data FROM events"),
            "contacts": rows("SELECT data FROM contacts"),
            "accounts": rows("SELECT data FROM accounts"),
            "appearances": rows("SELECT data FROM appearances"),
            "meta": {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT key, value FROM meta")} | {"app_version": VERSION},
            "decisions": [dict(r) for r in con.execute("SELECT * FROM decisions ORDER BY id")],
            "suppression": [dict(r) for r in con.execute("SELECT * FROM suppression")],
            "hubspot": [dict(r) for r in con.execute("SELECT * FROM hubspot_sync")],
            "log": [dict(r) for r in con.execute("SELECT * FROM events_log ORDER BY id DESC LIMIT 200")],
            "feedback_open": con.execute("SELECT COUNT(*) FROM feedback WHERE handled_at IS NULL").fetchone()[0],
        }


# ---------- decisions ----------

class Decision(BaseModel):
    object_type: Literal["contact", "account"]
    object_id: str = Field(max_length=200)
    decision: Literal["approve", "reject", "clear"]
    reason: str | None = Field(default=None, max_length=200)
    reviewer: str | None = Field(default=None, max_length=60)


@app.post("/api/decisions")
def decide(d: Decision):
    table = "contacts" if d.object_type == "contact" else "accounts"
    with db() as con:
        row = con.execute(f"SELECT score, lane FROM {table} WHERE id = ?", (d.object_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown lead")
        cur = con.execute(
            "INSERT INTO decisions (object_type, object_id, decision, reason, reviewer, suggested_lane, score, decided_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d.object_type, d.object_id, d.decision, d.reason, d.reviewer, row["lane"], row["score"], pipeline.now()),
        )
        saved = dict(con.execute("SELECT * FROM decisions WHERE id = ?", (cur.lastrowid,)).fetchone())
        con.commit()
    return saved


# ---------- do-not-contact list ----------

class Suppress(BaseModel):
    key: str = Field(max_length=200)
    label: str | None = Field(default=None, max_length=200)
    reason: str | None = Field(default=None, max_length=200)
    remove: bool = False


@app.post("/api/suppression")
def suppress(s: Suppress):
    with db() as con:
        if s.remove:
            con.execute("DELETE FROM suppression WHERE key = ?", (s.key,))
        else:
            con.execute("INSERT OR REPLACE INTO suppression VALUES (?, ?, ?, ?)", (s.key, s.label, s.reason, pipeline.now()))
        log(con, "suppression", f"{'Removed' if s.remove else 'Added'} {s.label or s.key} {'from' if s.remove else 'to'} the do-not-contact list")
        con.commit()
    return {"ok": True}


# ---------- versioned settings ----------

KINDS = ("scoring", "playbook:events", "playbook:sourcing", "playbook:profiling")


@app.get("/api/config")
def config_versions():
    with db() as con:
        out = {}
        for kind in KINDS:
            versions = [dict(r) for r in con.execute(
                "SELECT id, version, note, author, source, created_at, active, body FROM config_versions WHERE kind = ? ORDER BY version DESC", (kind,))]
            out[kind] = versions
        return out


KEYWORD = re.compile(r"(\\b)?[^\\\[\](){}*+?|^$.]{1,60}(\\b)?")


def validate_scoring(cfg):
    """Same structure as the repo's scoring.toml, numbers in range, keyword patterns that compile."""
    with db() as con:
        reference = json.loads(con.execute(
            "SELECT body FROM config_versions WHERE kind = 'scoring' AND source = 'repo' ORDER BY version DESC LIMIT 1").fetchone()["body"])
    errors = []

    def walk(ref, val, path):
        if isinstance(ref, dict):
            if not isinstance(val, dict):
                return errors.append(f"{path} should be a group")
            errors.extend(f"{path}.{k} isn't a known setting" for k in val if k not in ref)
            for k in ref:
                if k not in val:
                    errors.append(f"{path}.{k} is missing")
                else:
                    walk(ref[k], val[k], f"{path}.{k}")
        elif isinstance(ref, list):
            if not isinstance(val, list) or not all(isinstance(x, str) and x.strip() for x in val):
                return errors.append(f"{path} should be a list of words")
            # Plain words only, optionally wrapped in \\b for whole words: no patterns that could hang the server.
            errors.extend(f"{path}: '{kw}' should be a plain word or phrase" for kw in val if not KEYWORD.fullmatch(kw))
        elif isinstance(ref, (int, float)) and not isinstance(ref, bool):
            top = 365 if "days" in path else 3 if "multiplier" in path else 100
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not 0 <= val <= top:
                errors.append(f"{path} should be a number between 0 and {top}")
        elif isinstance(ref, str) and not isinstance(val, str):
            errors.append(f"{path} should be text")

    walk(reference, cfg, "scoring")
    if not errors and cfg["lanes"]["review"] >= cfg["lanes"]["fast_track"]:
        errors.append("The review threshold must be below the fast-track threshold")
    return errors


class NewVersion(BaseModel):
    kind: Literal["scoring", "playbook:events", "playbook:sourcing", "playbook:profiling"]
    body: str = Field(max_length=200_000)
    note: str = Field(max_length=300)
    author: str | None = Field(default=None, max_length=60)
    activate: bool = False


@app.post("/api/config")
def new_version(v: NewVersion):
    if v.kind == "scoring":
        try:
            cfg = json.loads(v.body)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Not valid settings: {e}")
        errors = validate_scoring(cfg)
        if errors:
            raise HTTPException(400, "; ".join(errors[:8]))
        body = json.dumps(cfg, ensure_ascii=False, indent=1)
    else:
        body = v.body
    with write_lock, db() as con:
        vid = pipeline.save_version(con, v.kind, body, v.note, v.author, "ui")
        version = con.execute("SELECT version FROM config_versions WHERE id = ?", (vid,)).fetchone()["version"]
        log(con, "config", f"{v.author or 'Someone'} saved {v.kind} v{version}: {v.note}")
        con.commit()
    if v.activate:
        return activate(vid)
    return {"id": vid, "version": version}


@app.post("/api/config/{version_id}/activate")
def activate(version_id: int):
    with write_lock, db() as con:
        row = con.execute("SELECT kind, version, body FROM config_versions WHERE id = ?", (version_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown version")
        if row["kind"] == "scoring":
            errors = validate_scoring(json.loads(row["body"]))
            if errors:
                raise HTTPException(400, "This version doesn't fit the current settings: " + "; ".join(errors[:5]))
        previous = con.execute("SELECT id FROM config_versions WHERE kind = ? AND active = 1", (row["kind"],)).fetchone()
        pipeline.activate_version(con, version_id)
        try:
            summary = pipeline.build(con=con) if row["kind"] == "scoring" else None
        except Exception as e:  # keep the previous version live if the new one can't score
            con.rollback()
            if previous:
                pipeline.activate_version(con, previous["id"])
                con.commit()
            raise HTTPException(400, f"Couldn't rescore with this version, so it wasn't activated: {e}")
        log(con, "config", f"Activated {row['kind']} v{row['version']}")
        con.commit()
    return {"ok": True, "kind": row["kind"], "version": row["version"], "rebuild": summary}


class Preview(BaseModel):
    body: str = Field(max_length=200_000)


@app.post("/api/scoring/preview")
def preview(p: Preview):
    try:
        cfg = json.loads(p.body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Not valid settings: {e}")
    errors = validate_scoring(cfg)
    if errors:
        raise HTTPException(400, "; ".join(errors[:8]))
    _, contacts, accounts, _ = pipeline.compute(cfg, dt.date.today())
    return {"contacts": {c["id"]: [c["score"], c["lane"]] for c in contacts},
            "accounts": {a["id"]: [a["score"], a["lane"]] for a in accounts}}


# ---------- feedback ----------

class Feedback(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    target: dict | None = None
    view: str | None = Field(default=None, max_length=60)
    author: str | None = Field(default=None, max_length=60)


@app.post("/api/feedback")
def feedback(f: Feedback):
    target = json.dumps(f.target, ensure_ascii=False)[:4000] if f.target else None
    with db() as con:
        cur = con.execute("INSERT INTO feedback (comment, target, view, author, created_at) VALUES (?, ?, ?, ?, ?)",
                          (f.comment, target, f.view, f.author, pipeline.now()))
        log(con, "feedback", f"{f.author or 'Someone'} left feedback on {f.view or 'the page'}")
        con.commit()
    return {"id": cur.lastrowid}


@app.get("/api/feedback")
def feedback_list(all: bool = False):
    with db() as con:
        sql = "SELECT * FROM feedback" + ("" if all else " WHERE handled_at IS NULL") + " ORDER BY id"
        return [dict(r) for r in con.execute(sql)]


# ---------- export and HubSpot ----------

def approved(con):
    """Approved, not suppressed: accounts, and contacts merged to one row per person (best-scoring appearance,
    with all their approved events)."""
    decisions = latest_decisions(con)
    suppressed = {r["key"] for r in con.execute("SELECT key FROM suppression")}
    events = {e["id"]: e for e in (json.loads(r["data"]) for r in con.execute("SELECT data FROM events"))}
    accounts = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM accounts")}
    contacts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM contacts")]
    ok = lambda kind, oid: decisions.get((kind, oid), {}).get("decision") == "approve"
    domain_ok = lambda a: (a.get("profile") or {}).get("domain") not in suppressed
    people = {}
    for c in contacts:
        if not ok("contact", c["id"]) or c["person_key"] in suppressed or c["id"] in suppressed:
            continue
        if c["account_id"] and not domain_ok(accounts.get(c["account_id"], {})):
            continue
        best = people.get(c["person_key"])
        events_seen = (best or {}).get("approved_events", []) + [c["event_id"]]
        if not best or c["score"] > best["score"]:
            best = c
        people[c["person_key"]] = best | {"approved_events": events_seen}
    approved_contacts = list(people.values())
    account_ids = {a for a in accounts if ok("account", a) and domain_ok(accounts[a])} | \
                  {c["account_id"] for c in approved_contacts if c["account_id"] in accounts}
    return events, [accounts[a] for a in account_ids], approved_contacts, accounts


def csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# HubSpot import: two files linked by "Company domain name". The gm_* columns map to the
# custom properties the API push creates (GM fit score, GM fit reasons, ...).
@app.get("/api/export/companies.csv")
def export_companies():
    with db() as con:
        events, accounts, _, _ = approved(con)
    header = ["Company name", "Company domain name", "Country/Region", "GM account id", "GM segment",
              "GM fit score", "GM fit reasons", "GM source events", "Industry (estimated)", "Employee band (estimated)", "ERP (public)"]
    rows = []
    for a in sorted(accounts, key=lambda a: -a["score"]):
        p = a.get("profile") or {}
        props = hubspot.company_props(a, events)
        rows.append([a["name"], p.get("domain") or "", p.get("hq_country") or "", a["id"], p.get("segment") or "",
                     a["score"], props["gm_fit_reasons"], props["gm_source_events"], p.get("industry") or "",
                     p.get("employees_band") or "", p.get("erp") or ""])
    return csv_response("hubspot-companies.csv", header, rows)


@app.get("/api/export/contacts.csv")
def export_contacts():
    with db() as con:
        events, _, contacts, accounts = approved(con)
    header = ["First name", "Last name", "Job title", "Company name", "Company domain name", "Email", "Lifecycle stage",
              "GM lead id", "GM fit score", "GM fit reasons", "GM source event", "GM source URL", "GM session at event"]
    rows = []
    for c in sorted(contacts, key=lambda c: -c["score"]):
        acct = accounts.get(c["account_id"]) or {}
        props = hubspot.contact_props(c, acct, events)
        rows.append([c["first_name"], c["last_name"], c.get("title") or "", props["company"],
                     (acct.get("profile") or {}).get("domain") or "", "", "lead", c["person_key"], c["score"],
                     props["gm_fit_reasons"], props["gm_source_event"], props["gm_source_url"], props["gm_session"]])
    return csv_response("hubspot-contacts.csv", header, rows)


@app.get("/api/hubspot/status")
def hubspot_status():
    with db() as con:
        last = con.execute("SELECT message, created_at FROM events_log WHERE kind = 'hubspot' ORDER BY id DESC LIMIT 1").fetchone()
        synced = con.execute("SELECT object_type, COUNT(*) n FROM hubspot_sync GROUP BY object_type").fetchall()
    return hubspot.status() | {"last_sync": dict(last) if last else None, "synced": {r["object_type"]: r["n"] for r in synced}}


@app.post("/api/hubspot/push")
def hubspot_push():
    if not write_lock.acquire(blocking=False):
        raise HTTPException(409, "A push or rebuild is already running")
    try:
        with db() as con:
            events, accounts, contacts, by_id = approved(con)
            try:
                summary = hubspot.push(con, accounts, contacts, by_id, events, pipeline.now())
            except (hubspot.HubSpotError, hubspot.httpx.HTTPError) as e:
                log(con, "hubspot", f"Push failed: {e}")
                con.commit()
                raise HTTPException(502, f"HubSpot: {e}")
            msg = (f"Pushed {summary['companies_created']} new and {summary['companies_updated']} updated companies, "
                   f"{summary['contacts_created']} new and {summary['contacts_updated']} updated contacts"
                   + (f"; {len(summary['errors'])} errors" if summary["errors"] else ""))
            log(con, "hubspot", msg, summary)
            con.commit()
        return summary | {"message": msg}
    finally:
        write_lock.release()


# ---------- copilot ----------

@app.get("/api/copilot/models")
def copilot_models():
    with db() as con:
        current = copilot.setting(con, "copilot_model")
    if not copilot.key():
        return {"configured": False, "current": current, "models": []}
    try:
        models = copilot.models()
        return {"configured": True, "current": current or copilot.default_model(), "models": models}
    except Exception as e:
        return {"configured": True, "current": current, "models": [], "error": str(e)[:200]}


class Setting(BaseModel):
    key: Literal["copilot_model"]
    value: str = Field(max_length=200)


@app.post("/api/settings")
def save_setting(s: Setting):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (s.key, s.value))
        log(con, "config", f"Copilot model set to {s.value}")
        con.commit()
    return {"ok": True}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class Chat(BaseModel):
    messages: list[ChatMessage] = Field(max_length=40)
    context: dict | None = None
    author: str | None = Field(default=None, max_length=60)


@app.post("/api/copilot")
def copilot_chat(c: Chat):
    with db() as con:
        try:
            out = copilot.chat(con, [m.model_dump() for m in c.messages], c.context or {}, latest_decisions, validate_scoring, c.author)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        question = next((m.content for m in reversed(c.messages) if m.role == "user"), "")
        con.execute("INSERT INTO copilot_log (author, question, reply, actions, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (c.author, question[:4000], out["reply"][:8000], json.dumps(out["actions"]), out["model"], pipeline.now()))
        for a in out["actions"]:
            log(con, "copilot", a)
        con.commit()
    return out
