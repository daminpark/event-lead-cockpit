"""The review cockpit: serves the page, records decisions, versions settings, exports and pushes to HubSpot."""

import csv
import datetime as dt
import hmac
import io
import json
import os
import re
import threading
import traceback
from contextlib import closing
from typing import Literal

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import copilot, hubspot, secrets_store, summaries
from pipeline import build as pipeline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "app", "static")
VERSION = open(os.path.join(ROOT, "VERSION")).read().strip()[:7] if os.path.exists(os.path.join(ROOT, "VERSION")) else "dev"

app = FastAPI(title="Event lead cockpit", docs_url=None, redoc_url=None)
write_lock = threading.Lock()  # one writer at a time for rebuilds and pushes

# The leads are real people, and the page can push to HubSpot and spend on the copilot,
# so everything sits behind a shared access code (sent with the link).
CODE = os.environ.get("COCKPIT_CODE", "").strip()              # shared with the team
OWNER_CODE = os.environ.get("COCKPIT_OWNER_CODE", "").strip()  # also manages keys and the copilot model
OPEN = os.environ.get("COCKPIT_ALLOW_OPEN") == "1"  # local development only
if not CODE and not OPEN:
    raise RuntimeError("Set COCKPIT_CODE (or COCKPIT_ALLOW_OPEN=1 for local development)")
OPEN_PATHS = {"/healthz", "/login", "/logout"}

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
<form method="post" action="login"><input type="hidden" name="next" id="next"><h1>Event Lead Cockpit</h1><p>Case study for GeneralMind. Please enter the access code from the email.</p>
ERROR<input name="code" type="password" autocomplete="current-password" autofocus placeholder="Access code"><button>Open</button></form>
<script>document.getElementById('next').value = location.hash</script></body></html>"""


def role_for(value):
    same = lambda a, b: bool(a and b) and hmac.compare_digest(a.encode(), b.encode())
    if same(value, OWNER_CODE):
        return "owner"
    if same(value, CODE):
        return "team"
    return "owner" if OPEN and not CODE else None


def record_error(source, message, detail=None, context=None, path=None, author=None):
    try:
        with db() as con:
            con.execute("INSERT INTO errors (source, message, detail, context, path, author, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (source, message[:1000], (detail or "")[:8000] or None,
                         json.dumps(context, ensure_ascii=False)[:20000] if context else None, path, author, pipeline.now()))
            con.commit()
    except Exception:
        pass  # never let error logging take the request down with it


@app.middleware("http")
async def require_code(request: Request, call_next):
    request.state.role = role_for(request.cookies.get("gm_code"))
    if request.url.path in OPEN_PATHS or request.state.role:
        try:
            resp = await call_next(request)
        except Exception as e:  # recorded with its path, so it shows up under Insights > Errors
            record_error("server", f"{type(e).__name__}: {e}", traceback.format_exc(), path=f"{request.method} {request.url.path}")
            resp = JSONResponse({"detail": "Something went wrong on the server. It has been recorded."}, status_code=500)
    elif request.url.path.startswith("/api/"):
        resp = JSONResponse({"detail": "Access code needed"}, status_code=401)
    else:
        resp = HTMLResponse(LOGIN_PAGE.replace("ERROR", ""), status_code=401)
    # Never let Cloudflare (or any shared cache) keep a copy of a page that sits behind the code.
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@app.post("/login")
def login(code: str = Form(max_length=200), next: str = Form(default="", max_length=400)):
    if not role_for(code.strip()):
        threading.Event().wait(1.5)  # slow down guessing
        return HTMLResponse(LOGIN_PAGE.replace("ERROR", '<div class="err">That code didn\'t work.</div>'), status_code=401)
    # back to the shared link the person opened (only in-app #/ links)
    resp = RedirectResponse("./" + (next if re.fullmatch(r"#/[A-Za-z0-9_\-./%]*", next) else ""), status_code=303)
    resp.set_cookie("gm_code", code.strip(), max_age=60 * 60 * 24 * 30, httponly=True, secure=True, samesite="lax")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("./", status_code=303)
    resp.delete_cookie("gm_code")
    return resp


def db():
    return closing(pipeline.connect(pipeline.DB))


def owner_only(request: Request):
    if request.state.role != "owner":
        raise HTTPException(403, "Only the owner can change this")


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
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/writeup")
def writeup():
    return FileResponse(os.path.join(STATIC, "writeup.html"))


@app.get("/writeup-pdf")  # no file extension, so Cloudflare doesn't cache it by default
def writeup_pdf():
    return FileResponse(os.path.join(STATIC, "writeup.pdf"), media_type="application/pdf",
                        filename="Pierre_Park_GeneralMind_case_study.pdf", content_disposition_type="inline")


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
def data(request: Request):
    with db() as con:
        rebuild_if_stale(con)
        rows = lambda sql: [json.loads(r["data"]) for r in con.execute(sql)]
        return {
            "events": [json.loads(r["data"]) | ({"summary": r["text"], "summary_model": r["model"], "summary_at": r["created_at"]} if r["text"] else {})
                       | ({"team": int(r["team"])} if r["team"] else {})
                       for r in con.execute("SELECT e.data, s.text, s.model, s.created_at, t.value AS team FROM events e "
                                            "LEFT JOIN event_summaries s ON s.event_id = e.id LEFT JOIN settings t ON t.key = 'team:' || e.id")],
            "contacts": rows("SELECT data FROM contacts"),
            "accounts": rows("SELECT data FROM accounts"),
            "appearances": rows("SELECT data FROM appearances"),
            "meta": {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT key, value FROM meta")} | {"app_version": VERSION, "role": request.state.role},
            "decisions": [dict(r) for r in con.execute("SELECT * FROM decisions ORDER BY id")],
            "suppression": [dict(r) for r in con.execute("SELECT * FROM suppression")],
            "hubspot": [dict(r) for r in con.execute("SELECT * FROM hubspot_sync")],
            "log": [dict(r) for r in con.execute("SELECT * FROM events_log ORDER BY id DESC LIMIT 200")],
            "feedback_open": con.execute("SELECT COUNT(*) FROM feedback WHERE handled_at IS NULL").fetchone()[0],
        }


# ---------- decisions ----------

class Decision(BaseModel):
    object_type: Literal["contact", "account", "event"]
    object_id: str = Field(max_length=200)
    decision: Literal["approve", "reject", "clear"]
    reason: str | None = Field(default=None, max_length=200)
    reviewer: str | None = Field(default=None, max_length=60)


@app.post("/api/decisions")
def decide(d: Decision):
    table = {"contact": "contacts", "account": "accounts", "event": "events"}[d.object_type]
    with db() as con:
        row = con.execute(f"SELECT score, lane FROM {table} WHERE id = ?", (d.object_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown lead")
        cur = con.execute(
            "INSERT INTO decisions (object_type, object_id, decision, reason, reviewer, suggested_lane, score, decided_at, scoring_version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.object_type, d.object_id, d.decision, d.reason, d.reviewer, row["lane"], row["score"], pipeline.now(),
             json.loads(con.execute("SELECT value FROM meta WHERE key = 'scoring_version'").fetchone()["value"])),
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
    events, contacts, accounts, _ = pipeline.compute(cfg, dt.date.today())
    return {"contacts": {c["id"]: [c["score"], c["lane"]] for c in contacts},
            "accounts": {a["id"]: [a["score"], a["lane"]] for a in accounts},
            "events": {i: [e["score"], e["lane"]] for i, e in events.items()}}


# ---------- feedback ----------

class Feedback(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)
    target: dict | None = None
    view: str | None = Field(default=None, max_length=60)
    author: str | None = Field(default=None, max_length=60)
    context: dict | None = None  # recent actions and app state when the note was written


@app.post("/api/feedback")
def feedback(f: Feedback):
    target = json.dumps(f.target, ensure_ascii=False)[:4000] if f.target else None
    with db() as con:
        context = json.dumps(f.context, ensure_ascii=False)[:20000] if f.context else None
        cur = con.execute("INSERT INTO feedback (comment, target, view, author, created_at, context) VALUES (?, ?, ?, ?, ?, ?)",
                          (f.comment, target, f.view, f.author, pipeline.now(), context))
        log(con, "feedback", f"{f.author or 'Someone'} left feedback on {f.view or 'the page'}")
        con.commit()
    return {"id": cur.lastrowid}


@app.get("/api/feedback")
def feedback_list(all: bool = False):
    with db() as con:
        sql = "SELECT * FROM feedback" + ("" if all else " WHERE status IN ('open', 'planned')") + " ORDER BY id DESC"
        return [dict(r) for r in con.execute(sql)]


class NoteUpdate(BaseModel):
    comment: str | None = Field(default=None, min_length=1, max_length=4000)
    status: Literal["open", "planned", "done", "wontfix"] | None = None
    handled_note: str | None = Field(default=None, max_length=1000)
    author: str | None = Field(default=None, max_length=60)


@app.patch("/api/feedback/{note_id}")
def feedback_update(note_id: int, u: NoteUpdate):
    with db() as con:
        row = con.execute("SELECT * FROM feedback WHERE id = ?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown note")
        status = u.status or row["status"]
        con.execute("UPDATE feedback SET comment = ?, status = ?, handled_note = ?, handled_at = ? WHERE id = ?",
                    (u.comment if u.comment is not None else row["comment"], status,
                     u.handled_note if u.handled_note is not None else row["handled_note"],
                     (row["handled_at"] or pipeline.now()) if status in ("done", "wontfix") else None, note_id))
        changes = ", ".join(k for k, v in (("text", u.comment), ("status " + (u.status or ""), u.status), ("what was done", u.handled_note)) if v is not None)
        log(con, "feedback", f"{u.author or 'Someone'} updated feedback #{note_id}: {changes}")
        con.commit()
        return dict(con.execute("SELECT * FROM feedback WHERE id = ?", (note_id,)).fetchone())


@app.delete("/api/feedback/{note_id}", dependencies=[Depends(owner_only)])
def feedback_delete(note_id: int):
    with db() as con:
        con.execute("DELETE FROM feedback WHERE id = ?", (note_id,))
        log(con, "feedback", f"Deleted feedback #{note_id}")
        con.commit()
    return {"ok": True}


_compare_cache = {}


@app.get("/api/scoring/compare")
def compare_versions():
    """Replay every scoring version against every reviewer decision: the regression test for settings."""
    with db() as con:
        versions = [dict(r) for r in con.execute(
            "SELECT id, version, note, author, source, created_at, active, body FROM config_versions WHERE kind = 'scoring' ORDER BY version DESC LIMIT 12")]
        decisions = latest_decisions(con)
        made_under = {}
        for (kind, _), d in decisions.items():
            if kind == "contact" and d.get("scoring_version") is not None:
                made_under.setdefault(d["scoring_version"], []).append(d)
    contact_decisions = {oid: d["decision"] for (kind, oid), d in decisions.items() if kind == "contact"}
    today = dt.date.today()
    out = []
    for v in versions:
        key = (v["id"], today.isoformat())
        if key not in _compare_cache:
            try:
                _, contacts, _, _ = pipeline.compute(json.loads(v["body"]), today)
                _compare_cache[key] = {c["id"]: c["lane"] for c in contacts}
            except (KeyError, TypeError):
                _compare_cache[key] = None
        lanes = _compare_cache[key]
        row = {k: v[k] for k in ("version", "note", "author", "source", "created_at", "active")}
        if lanes is None:
            out.append(row | {"error": "doesn't fit the current settings"})
            continue
        agree = n = 0
        for oid, dec in contact_decisions.items():
            lane = lanes.get(oid)
            if lane == "fast_track":
                n += 1; agree += dec == "approve"
            elif lane in ("filtered", "competitor"):
                n += 1; agree += dec == "reject"
        live = made_under.get(v["version"], [])
        row |= {"fast_track": sum(1 for l in lanes.values() if l == "fast_track"),
                "replay_agreement": round(100 * agree / n) if n else None, "replay_n": n,
                "decided_while_active": len(live),
                "approved_while_active": sum(1 for d in live if d["decision"] == "approve")}
        out.append(row)
    return out


# ---------- export and HubSpot ----------

def approved(con, only=None):
    """Approved, not suppressed: accounts, and contacts merged to one row per person (best-scoring appearance,
    with all their approved events)."""
    decisions = latest_decisions(con)
    suppressed = {r["key"] for r in con.execute("SELECT key FROM suppression")}
    events = {e["id"]: e for e in (json.loads(r["data"]) for r in con.execute("SELECT data FROM events"))}
    accounts = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM accounts")}
    contacts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM contacts")]
    ok = lambda kind, oid: decisions.get((kind, oid), {}).get("decision") == "approve"
    domain_ok = lambda a: (a.get("profile") or {}).get("domain") not in suppressed
    # A selected listing brings every approved listing of the same person, so HubSpot gets all their events.
    keys = {c["person_key"] for c in contacts if c["id"] in only} if only is not None else None
    people = {}
    for c in contacts:
        if not ok("contact", c["id"]) or c["person_key"] in suppressed or c["id"] in suppressed:
            continue
        if keys is not None and c["person_key"] not in keys:
            continue
        if c["account_id"] and not domain_ok(accounts.get(c["account_id"], {})):
            continue
        best = people.get(c["person_key"])
        events_seen = (best or {}).get("approved_events", []) + [c["event_id"]]
        listing_ids = (best or {}).get("approved_ids", []) + [c["id"]]
        if not best or c["score"] > best["score"]:
            best = c
        people[c["person_key"]] = best | {"approved_events": events_seen, "approved_ids": listing_ids}
    approved_contacts = list(people.values())
    # Companies go to HubSpot with their approved people; company-only approvals only in a full push.
    account_ids = ({a for a in accounts if ok("account", a) and domain_ok(accounts[a])} if only is None else set()) | \
                  {c["account_id"] for c in approved_contacts if c["account_id"] in accounts}
    return events, [accounts[a] for a in account_ids], approved_contacts, accounts


def csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/export/contacts.csv")
def export_contacts(event: str | None = None):
    with db() as con:
        events, _, contacts, accounts = approved(con)
    if event:  # one or more events' approved people (comma-separated ids), for that meeting list
        wanted = set(event.split(","))
        contacts = [c for c in contacts if wanted & set(c.get("approved_events") or [c["event_id"]])]
    header = ["First name", "Last name", "Job title", "Company name", "Company domain name", "Email", "Lifecycle stage",
              "GM lead id", "GM fit score", "GM fit reasons", "GM source event", "GM source URL", "GM session at event"]
    rows = []
    for c in sorted(contacts, key=lambda c: -c["score"]):
        acct = accounts.get(c["account_id"]) or {}
        props = hubspot.contact_props(c, acct, events)
        rows.append([c["first_name"], c["last_name"], c.get("title") or "", props["company"],
                     (acct.get("profile") or {}).get("domain") or "", "", "lead", c["person_key"], c["score"],
                     props["gm_fit_reasons"], props["gm_source_event"], props["gm_source_url"], props["gm_session"]])
    return csv_response(f"hubspot-contacts{'-' + re.sub(r'[^a-z0-9-]', '', event)[:60] if event else ''}.csv", header, rows)


@app.get("/api/hubspot/status")
def hubspot_status(fresh: bool = False):
    with db() as con:
        last = con.execute("SELECT message, created_at FROM events_log WHERE kind = 'hubspot' ORDER BY id DESC LIMIT 1").fetchone()
        synced = con.execute("SELECT object_type, COUNT(*) n FROM hubspot_sync GROUP BY object_type").fetchall()
    return hubspot.status(fresh) | {"checked_at": pipeline.now(), "last_sync": dict(last) if last else None, "synced": {r["object_type"]: r["n"] for r in synced}}


class Push(BaseModel):
    contact_ids: list[str] | None = Field(default=None, max_length=2000)  # None: everything approved


@app.post("/api/hubspot/push")
def hubspot_push(p: Push | None = None):
    if not write_lock.acquire(blocking=False):
        raise HTTPException(409, "A push or rebuild is already running")
    try:
        with db() as con:
            events, accounts, contacts, by_id = approved(con, set(p.contact_ids) if p and p.contact_ids is not None else None)
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
    key: Literal["copilot_model", "copilot_effort"]
    value: str = Field(max_length=200)


@app.post("/api/settings", dependencies=[Depends(owner_only)])
def save_setting(s: Setting):
    if s.key == "copilot_effort" and s.value not in ("low", "medium", "high"):
        raise HTTPException(400, "Effort is low, medium or high")
    with db() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (s.key, s.value))
        log(con, "config", f"Copilot {'model' if s.key == 'copilot_model' else 'thinking effort'} set to {s.value}")
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
            log(con, "copilot", a["text"])
        con.commit()
    return out


# ---------- settings: keys and connections ----------

@app.get("/api/settings")
def settings(request: Request):
    with db() as con:
        model = copilot.setting(con, "copilot_model")
        effort = copilot.setting(con, "copilot_effort") or "medium"
    return {"role": request.state.role, "hubspot": secrets_store.status("hubspot"),
            "openrouter": secrets_store.status("openrouter") | {"health": secrets_store.health("openrouter")},
            "copilot_model": model, "copilot_effort": effort}


class Secret(BaseModel):
    name: Literal["hubspot", "openrouter"]
    value: str = Field(default="", max_length=400)


@app.post("/api/settings/secret", dependencies=[Depends(owner_only)])
def save_secret(sec: Secret):
    error = secrets_store.put(sec.name, sec.value)
    if error:
        raise HTTPException(400, error)
    hubspot.reset_status()
    with db() as con:
        log(con, "config", f"{'Saved' if sec.value.strip() else 'Removed'} the {'HubSpot token' if sec.name == 'hubspot' else 'OpenRouter key'}")
        con.commit()
    return secrets_store.status(sec.name)


# ---------- errors ----------

CLIENT_ERRORS = {"window": 3600, "max": 300, "at": []}


class ClientError(BaseModel):
    message: str = Field(max_length=1000)
    detail: str | None = Field(default=None, max_length=8000)
    context: dict | None = None
    author: str | None = Field(default=None, max_length=60)


@app.post("/api/errors")
def client_error(e: ClientError):
    now = dt.datetime.now().timestamp()
    CLIENT_ERRORS["at"] = [t for t in CLIENT_ERRORS["at"] if now - t < CLIENT_ERRORS["window"]]
    if len(CLIENT_ERRORS["at"]) < CLIENT_ERRORS["max"]:
        CLIENT_ERRORS["at"].append(now)
        record_error("client", e.message, e.detail, e.context, path=(e.context or {}).get("state", {}).get("view"), author=e.author)
    return {"ok": True}


@app.get("/api/errors")
def errors_list():
    with db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM errors ORDER BY id DESC LIMIT 50")]


@app.post("/api/errors/{error_id}/resolved")
def error_resolved(error_id: int):
    with db() as con:
        con.execute("UPDATE errors SET resolved_at = ? WHERE id = ?", (pipeline.now(), error_id))
        con.commit()
    return {"ok": True}



class Remove(BaseModel):
    contact_id: str = Field(max_length=200)


@app.post("/api/hubspot/remove", dependencies=[Depends(owner_only)])
def hubspot_remove(r: Remove):
    """Undo a send: the person goes back to Approved here, and to HubSpot's recycle bin there."""
    with write_lock, db() as con:
        row = con.execute("SELECT data FROM contacts WHERE id = ?", (r.contact_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown person")
        c = json.loads(row["data"])
        try:
            out = hubspot.remove_person(con, c["person_key"], c.get("account_id"))
        except (hubspot.HubSpotError, hubspot.httpx.HTTPError) as e:
            raise HTTPException(502, f"HubSpot: {e}")
        log(con, "hubspot", f"Removed {c['name']} from HubSpot ({', '.join(f'{k} {v}' for k, v in out.items()) or 'nothing to remove'})", out)
        con.commit()
    return {"ok": True, "removed": out, "name": c["name"]}



# ---------- event summaries ----------

@app.post("/api/events/{event_id}/summary")
def event_summary(event_id: str):
    with db() as con:
        try:
            return summaries.summarize(con, event_id)
        except RuntimeError as e:
            raise HTTPException(400, str(e))



# ---------- playbook editor ----------

class PlaybookChat(BaseModel):
    messages: list[ChatMessage] = Field(max_length=40)
    draft: str = Field(max_length=40000)
    author: str | None = Field(default=None, max_length=60)


@app.post("/api/playbooks/{kind}/chat")
def playbook_chat(kind: Literal["events", "sourcing", "profiling"], c: PlaybookChat):
    with db() as con:
        try:
            out = copilot.playbook_chat(con, kind, [m.model_dump() for m in c.messages], c.draft, c.author)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        question = next((m.content for m in reversed(c.messages) if m.role == "user"), "")
        con.execute("INSERT INTO copilot_log (author, question, reply, actions, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (c.author, f"[playbook:{kind}] {question}"[:4000], out["reply"][:8000],
                     json.dumps([out["summary"]] if out["draft"] else []), out["model"], pipeline.now()))
        con.commit()
    return out



class Team(BaseModel):
    people: int = Field(ge=1, le=10)


@app.post("/api/events/{event_id}/team")
def event_team(event_id: str, t: Team):
    """How many people we'd send: sets this event's meeting plan."""
    with db() as con:
        if not con.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone():
            raise HTTPException(404, "Unknown event")
        con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (f"team:{event_id}", str(t.people)))
        log(con, "config", f"Team for {event_id} set to {t.people}")
        con.commit()
    return {"ok": True}
