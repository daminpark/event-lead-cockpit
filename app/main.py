"""The review cockpit: serves the page, records decisions, exports approved leads for HubSpot."""

import csv
import datetime as dt
import io
import json
import os
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("COCKPIT_DB", os.path.join(ROOT, "data", "cockpit.db"))
STATIC = os.path.join(ROOT, "app", "static")

app = FastAPI(title="GeneralMind event lead cockpit", docs_url=None, redoc_url=None)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def latest_decisions(con):
    rows = con.execute(
        "SELECT * FROM decisions WHERE id IN (SELECT MAX(id) FROM decisions GROUP BY object_type, object_id)"
    ).fetchall()
    return {(r["object_type"], r["object_id"]): dict(r) for r in rows if r["decision"] != "clear"}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/data")
def data():
    with db() as con:
        events = [json.loads(r["data"]) for r in con.execute("SELECT data FROM events")]
        contacts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM contacts")]
        accounts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM accounts")]
        appearances = [json.loads(r["data"]) for r in con.execute("SELECT data FROM appearances")]
        meta = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT key, value FROM meta")}
        decisions = [dict(r) for r in con.execute("SELECT * FROM decisions ORDER BY id")]
    return {"events": events, "contacts": contacts, "accounts": accounts, "appearances": appearances,
            "decisions": decisions, "meta": meta}


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
            (d.object_type, d.object_id, d.decision, d.reason, d.reviewer, row["lane"], row["score"],
             dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")),
        )
        saved = dict(con.execute("SELECT * FROM decisions WHERE id = ?", (cur.lastrowid,)).fetchone())
    return saved


def csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def approved(con):
    decisions = latest_decisions(con)
    events = {json.loads(r["data"])["id"]: json.loads(r["data"]) for r in con.execute("SELECT data FROM events")}
    accounts = {r["id"]: json.loads(r["data"]) for r in con.execute("SELECT id, data FROM accounts")}
    contacts = [json.loads(r["data"]) for r in con.execute("SELECT data FROM contacts")]
    ok = lambda kind, oid: decisions.get((kind, oid), {}).get("decision") == "approve"
    approved_contacts = [c for c in contacts if ok("contact", c["id"])]
    account_ids = {a for a in accounts if ok("account", a)} | {c["account_id"] for c in approved_contacts if c["account_id"]}
    return events, [accounts[a] for a in account_ids if a in accounts], approved_contacts, accounts


def reasons_text(reasons):
    return "; ".join(f"{r['label']} (+{r['points']})" for r in reasons if r["points"])


# HubSpot import: two files linked by "Company domain name". Columns beyond HubSpot's defaults
# map to custom properties created once (gm_fit_score, gm_fit_reasons, gm_lead_event, ...).
@app.get("/api/export/companies.csv")
def export_companies():
    with db() as con:
        events, accounts, _, _ = approved(con)
    header = ["Company name", "Company domain name", "Industry (GM)", "Country/Region", "Employee band",
              "ERP", "Segment", "Lead source", "Source events", "Fit score", "Fit reasons"]
    rows = []
    for a in sorted(accounts, key=lambda a: -a["score"]):
        p = a.get("profile") or {}
        rows.append([a["name"], p.get("domain") or "", p.get("industry") or "", p.get("hq_country") or "",
                     p.get("employees_band") or "", p.get("erp") or "", p.get("segment") or "", "Event sourcing",
                     " | ".join(events[e]["name"] for e in a["events"] if e in events), a["score"],
                     reasons_text(a["reasons"])])
    return csv_response("hubspot-companies.csv", header, rows)


@app.get("/api/export/contacts.csv")
def export_contacts():
    with db() as con:
        events, _, contacts, accounts = approved(con)
    header = ["First name", "Last name", "Job title", "Company name", "Company domain name", "Email",
              "Lead source", "Event", "Event date", "Role at event", "Session", "Source URL", "Fit score", "Fit reasons"]
    rows = []
    for c in sorted(contacts, key=lambda c: -c["score"]):
        acct = accounts.get(c["account_id"]) or {}
        p = acct.get("profile") or {}
        ev = events.get(c["event_id"], {})
        rows.append([c["first_name"], c["last_name"], c.get("title") or "", acct.get("name") or c.get("company") or "",
                     p.get("domain") or "", "", "Event sourcing", ev.get("name", ""), ev.get("start", ""),
                     c.get("role_at_event") or "", c.get("session") or "", c.get("source_url") or "", c["score"],
                     reasons_text(c["reasons"])])
    return csv_response("hubspot-contacts.csv", header, rows)
