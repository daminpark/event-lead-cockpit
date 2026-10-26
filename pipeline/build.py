"""Build the cockpit database from extracted event leads and company profiles.

    python3 pipeline/build.py [--today 2026-10-26]

Re-runnable: leads and scores are rebuilt from data/, reviewer decisions are kept
(they're keyed by stable ids), so you can add an event or change scoring.toml and
rebuild without losing anyone's reviews.
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import tomllib
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DB = os.environ.get("COCKPIT_DB", os.path.join(DATA, "cockpit.db"))

LEGAL = re.compile(
    r"\b(ag|gmbh|se|kgaa|kg|co|ohg|mbh|ltd|limited|inc|plc|llc|sa|s a|spa|bv|b v|nv|n v|ab|as|oy|group|gruppe|holding|international|deutschland|germany)\b"
)
ACADEMIC = re.compile(r"^(prof\.?|dr\.?|dr\.-ing\.?|dipl\.-?\w*\.?|ing\.?|mag\.?|mba|phd)$", re.I)


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def company_key(name: str) -> str:
    s = ascii_fold(name.lower()).replace("&", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", LEGAL.sub(" ", s)).strip()


def slug(*parts: str) -> str:
    s = ascii_fold(" ".join(parts).lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:90]


def text_norm(s: str) -> str:
    s = ascii_fold(s.lower()).replace("‐", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s)


def split_name(name: str):
    tokens = [t for t in name.replace(",", " ").split() if not ACADEMIC.match(t)]
    if not tokens:
        return name, ""
    return tokens[0], " ".join(tokens[1:])


def matches(text: str, keywords) -> list:
    hits = []
    for kw in keywords:
        if kw.startswith("\\b"):
            if re.search(kw, text):
                hits.append(kw.replace("\\b", ""))
        elif kw in text:
            hits.append(kw)
    return hits


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"skip {os.path.relpath(path, ROOT)}: {e}")
        return default


def load_profiles():
    by_alias, by_key = {}, {}
    for path in sorted(glob.glob(os.path.join(DATA, "profiles", "batch-*.json"))):
        for p in load_json(path, []):
            for alias in p.get("aliases") or [p.get("name", "")]:
                by_alias[alias] = p
                by_key.setdefault(company_key(alias), p)
            if p.get("name"):
                by_key.setdefault(company_key(p["name"]), p)
    return by_alias, by_key


def source_texts(event_id: str) -> str:
    parts = []
    for path in glob.glob(os.path.join(DATA, "sources", event_id, "*.txt")):
        with open(path, encoding="utf-8", errors="replace") as f:
            parts.append(f.read())
    return text_norm("\n".join(parts))


def found_in_source(name: str, text: str) -> str:
    n = text_norm(name)
    if n and n in text:
        return "exact"
    first, last = split_name(name)
    if last and text_norm(last) in text and text_norm(first) in text:
        return "partial"
    return "missing"


def score_role(title: str, session: str, cfg):
    reasons, tags, total = [], [], 0
    t = (title or "").lower()
    best = None
    for key, fn in cfg["role"]["functions"].items():
        if matches(t, fn["keywords"]) and (best is None or fn["points"] > best[1]["points"]):
            best = (key, fn)
    if best:
        total += best[1]["points"]
        reasons.append({"label": best[1]["label"], "points": best[1]["points"], "kind": "role"})
        tags.append(f"function:{best[0]}")
    elif t:
        reasons.append({"label": "Function outside target buyers", "points": 0, "kind": "role"})
        tags.append("function:none")
    sen = cfg["role"]["seniority"]
    level = next((k for k in ("c_level", "head", "manager") if matches(t, sen[k]["keywords"])), None)
    if level:
        total += sen[level]["points"]
        reasons.append({"label": sen[level]["label"], "points": sen[level]["points"], "kind": "role"})
        tags.append(f"seniority:{level}")
    elif t:
        total += sen["other_points"]
        reasons.append({"label": "Not a decision-maker title", "points": sen["other_points"], "kind": "role"})
        tags.append("seniority:other")
    else:
        reasons.append({"label": "No job title on the source page", "points": 0, "kind": "role"})
        tags.append("seniority:unknown")
    interest = cfg["role"]["interest"]
    if matches(f"{t} {(session or '').lower()}", interest["keywords"]):
        total += interest["points"]
        reasons.append({"label": interest["label"], "points": interest["points"], "kind": "role"})
        tags.append("interest:yes")
    return total, reasons, tags


def score_company(profile, cfg):
    c = cfg["company"]
    if not profile:
        return 0, [{"label": "Company not profiled yet", "points": 0, "kind": "company"}], ["segment:unknown"]
    reasons, tags, total = [], [f"segment:{profile.get('segment', 'unknown')}"], 0
    if profile.get("segment") == "buyer":
        total += c["buyer_points"]
        reasons.append({"label": "Operating company (potential buyer)", "points": c["buyer_points"], "kind": "company"})
    industry = (profile.get("industry") or "").strip()
    if industry:
        core = any(k in industry.lower() for k in c["core_industries"])
        pts = c["core_industry_points"] if core else c["other_industry_points"]
        total += pts
        reasons.append({"label": f"{industry}{' (core industry)' if core else ''}", "points": pts, "kind": "company"})
        tags.append(f"industry:{industry}")
    band = profile.get("employees_band") or "unknown"
    pts = c["size_points"].get(band, c["size_points"]["unknown"])
    total += pts
    reasons.append({"label": f"Employees {band}" if band != "unknown" else "Size unknown", "points": pts, "kind": "company"})
    tags.append(f"size:{band}")
    if profile.get("dach"):
        total += c["dach_points"]
        reasons.append({"label": f"Based in DACH ({profile.get('hq_country') or '?'})", "points": c["dach_points"], "kind": "company"})
        tags.append("dach:yes")
    erp = profile.get("erp") or "unknown"
    if erp not in ("unknown", "Other"):
        total += c["erp_points"]
        reasons.append({"label": f"Runs {erp} (public)", "points": c["erp_points"], "kind": "company"})
        tags.append(f"erp:{erp}")
    return total, reasons, tags


def score_event(role_at_event: str, event, today, cfg):
    e = cfg["event"]
    reasons, total = [], 0
    if role_at_event in ("keynote", "speaker", "panelist"):
        total += e["speaker_points"]
        reasons.append({"label": f"{role_at_event.capitalize()} at {event['short']}", "points": e["speaker_points"], "kind": "event"})
    elif role_at_event in ("moderator", "chair"):
        total += e["moderator_points"]
        reasons.append({"label": f"{role_at_event.capitalize()} at {event['short']}", "points": e["moderator_points"], "kind": "event"})
    days = (dt.date.fromisoformat(event["start"]) - today).days
    if days <= e["soon_days"]:
        pts, label = e["soon_points"], f"Event in {days} days"
    elif days <= e["later_days"]:
        pts, label = e["later_points"], f"Event in {days} days"
    else:
        pts, label = e["far_points"], f"Event in {days // 30} months"
    total += pts
    reasons.append({"label": label, "points": pts, "kind": "event"})
    if event.get("generalmind_present"):
        total += e["generalmind_present_points"]
        reasons.append({"label": "GeneralMind has a stand there", "points": e["generalmind_present_points"], "kind": "event"})
    return total, reasons


def lane_for(profile, score, confidence, cfg):
    if profile and profile.get("existing_customer"):
        return "customer"
    seg = (profile or {}).get("segment")
    if seg == "competitor":
        return "competitor"
    if seg == "partner":
        return "partner"
    if seg in ("vendor", "other"):
        return "filtered"
    if score >= cfg["lanes"]["fast_track"] and confidence != "low":
        return "fast_track"
    if score >= cfg["lanes"]["review"] or seg is None:
        return "review"
    return "filtered"


SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_type TEXT NOT NULL,          -- contact | account
  object_id TEXT NOT NULL,
  decision TEXT NOT NULL,             -- approve | reject | clear
  reason TEXT,
  reviewer TEXT,
  suggested_lane TEXT,                -- what the scoring suggested at the time
  score INTEGER,
  decided_at TEXT NOT NULL
);
-- Scoring settings and playbooks are versioned data: every save is a new row, one row per kind is active.
CREATE TABLE IF NOT EXISTS config_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                 -- scoring | playbook:events | playbook:sourcing | playbook:profiling
  version INTEGER NOT NULL,
  body TEXT NOT NULL,
  note TEXT,
  author TEXT,
  source TEXT NOT NULL,               -- repo | ui
  created_at TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  comment TEXT NOT NULL,
  target TEXT,                        -- the element picked on the page, as JSON
  view TEXT,
  author TEXT,
  created_at TEXT NOT NULL,
  handled_at TEXT,
  handled_note TEXT
);
CREATE TABLE IF NOT EXISTS suppression (
  key TEXT PRIMARY KEY,               -- contact id or company domain
  label TEXT,
  reason TEXT,
  added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hubspot_sync (
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  hubspot_id TEXT NOT NULL,
  synced_at TEXT NOT NULL,
  PRIMARY KEY (object_type, object_id)
);
CREATE TABLE IF NOT EXISTS events_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                 -- build | config | hubspot | feedback
  message TEXT NOT NULL,
  data TEXT,
  created_at TEXT NOT NULL
);
"""

LEAD_TABLES = """
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS contacts;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS appearances;
DROP TABLE IF EXISTS meta;
CREATE TABLE events (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE contacts (id TEXT PRIMARY KEY, account_id TEXT, event_id TEXT, score INTEGER, lane TEXT, data TEXT NOT NULL);
CREATE TABLE accounts (id TEXT PRIMARY KEY, score INTEGER, lane TEXT, data TEXT NOT NULL);
CREATE TABLE appearances (account_id TEXT, event_id TEXT, role TEXT, data TEXT NOT NULL);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

PLAYBOOKS = {"playbook:events": "events.md", "playbook:sourcing": "sourcing.md", "playbook:profiling": "profiling.md"}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def connect(path=DB):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def repo_configs():
    with open(os.path.join(ROOT, "scoring.toml"), "rb") as f:
        configs = {"scoring": json.dumps(tomllib.load(f), ensure_ascii=False, indent=1)}
    for kind, name in PLAYBOOKS.items():
        with open(os.path.join(ROOT, "playbooks", name), encoding="utf-8") as f:
            configs[kind] = f.read()
    return configs


def sync_repo_configs(con):
    """A changed file in the repo becomes a new version. It's activated only if the active
    version also came from the repo, so a version someone chose in the cockpit is never overridden."""
    for kind, body in repo_configs().items():
        latest_repo = con.execute(
            "SELECT body FROM config_versions WHERE kind = ? AND source = 'repo' ORDER BY version DESC LIMIT 1", (kind,)
        ).fetchone()
        if latest_repo and latest_repo["body"] == body:
            continue
        active = con.execute("SELECT source FROM config_versions WHERE kind = ? AND active = 1", (kind,)).fetchone()
        save_version(con, kind, body, "From the repository", "repo", "repo", activate=active is None or active["source"] == "repo")


def save_version(con, kind, body, note, author, source, activate=False):
    version = (con.execute("SELECT MAX(version) FROM config_versions WHERE kind = ?", (kind,)).fetchone()[0] or 0) + 1
    cur = con.execute(
        "INSERT INTO config_versions (kind, version, body, note, author, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (kind, version, body, note, author, source, now()),
    )
    if activate:
        activate_version(con, cur.lastrowid)
    return cur.lastrowid


def activate_version(con, version_id):
    kind = con.execute("SELECT kind FROM config_versions WHERE id = ?", (version_id,)).fetchone()["kind"]
    con.execute("UPDATE config_versions SET active = (id = ?) WHERE kind = ?", (version_id, kind))


def active_scoring(con):
    row = con.execute("SELECT id, version, body FROM config_versions WHERE kind = 'scoring' AND active = 1").fetchone()
    return json.loads(row["body"]), row["version"]


def compute(cfg, today):
    """Score every contact and account with the given settings. Pure: writes nothing except the
    source-check file when the saved pages are present."""
    events = {e["id"]: e for e in load_json(os.path.join(DATA, "events.json"), [])}
    for e in events.values():
        e["short"] = re.sub(r"\s*\(.*?\)|\s+20\d\d.*$", "", e["name"]).strip()
    by_alias, by_key = load_profiles()
    briefs = {}
    for path in sorted(glob.glob(os.path.join(DATA, "briefs", "*.json"))):
        for b in load_json(path, []):
            if b.get("id"):
                briefs[b["id"]] = b

    def profile_for(name):
        return by_alias.get(name) or by_key.get(company_key(name))

    # The saved pages stay out of git, so their check results are kept in a small committed file
    # that a server can build from.
    checks_path = os.path.join(DATA, "source_checks.json")
    have_sources = os.path.isdir(os.path.join(DATA, "sources"))
    checks = {} if have_sources else load_json(checks_path, {})

    contacts, accounts, appearances = [], {}, []

    def account_for(name):
        profile = profile_for(name)
        display = (profile or {}).get("name") or name
        aid = slug(company_key(display) or display)
        if aid not in accounts:
            accounts[aid] = {"id": aid, "name": display, "profile": profile, "events": set(), "contacts": [], "roles": set()}
        return accounts[aid]

    for path in sorted(glob.glob(os.path.join(DATA, "extracted", "*.json"))):
        ex = load_json(path, None)
        if not ex or ex.get("event_id") not in events:
            continue
        event = events[ex["event_id"]]
        text = source_texts(event["id"]) if have_sources else ""
        seen = set()
        for p in ex.get("people", []):
            if not p.get("name"):
                continue
            cid = slug(event["id"], p["name"])
            if cid in seen:
                continue
            seen.add(cid)
            company = p.get("company") or ""
            acct = account_for(company) if company else None
            profile = acct["profile"] if acct else None
            r_pts, r_reasons, r_tags = score_role(p.get("title"), p.get("session"), cfg)
            c_pts, c_reasons, c_tags = score_company(profile, cfg)
            e_pts, e_reasons = score_event(p.get("role_at_event", "speaker"), event, today, cfg)
            score = min(100, r_pts + c_pts + e_pts)
            if have_sources:
                checks[cid] = found_in_source(p["name"], text)
            check = checks.get(cid, "missing")
            confidence, conf_notes = "high", []
            if "previous" in (p.get("edition") or ""):
                confidence = "medium"
                conf_notes.append(f"Listed at the {p['edition'].replace(' (previous)', '')} edition; this year's list isn't out yet")
            if profile is None or profile.get("confidence") == "low":
                confidence = "medium" if confidence == "high" else confidence
                conf_notes.append("Company profile is uncertain")
            if check == "missing":
                confidence = "low"
                conf_notes.append("Name not found in the saved source page")
            first, last = split_name(p["name"])
            contact = {
                "id": cid, "name": p["name"], "first_name": first, "last_name": last,
                "title": p.get("title"), "company": company, "account_id": acct["id"] if acct else None,
                "event_id": event["id"], "role_at_event": p.get("role_at_event"), "session": p.get("session"),
                "source_url": p.get("source_url"), "edition": p.get("edition"), "source_check": check,
                "score": score, "role_fit": r_pts, "company_fit": c_pts, "event_fit": e_pts,
                "reasons": r_reasons + c_reasons + e_reasons, "tags": r_tags + c_tags + [f"event:{event['id']}"],
                "confidence": confidence, "confidence_notes": conf_notes,
                "brief": briefs.get(cid, {}).get("brief"), "opener": briefs.get(cid, {}).get("opener"),
            }
            contact["lane"] = lane_for(profile, score, confidence, cfg)
            contacts.append(contact)
            if acct:
                acct["events"].add(event["id"])
                acct["contacts"].append(contact)
                acct["roles"].add(p.get("role_at_event") or "speaker")
        for c in ex.get("companies", []):
            if not c.get("name"):
                continue
            acct = account_for(c["name"])
            acct["events"].add(event["id"])
            acct["roles"].add(c.get("role_at_event") or "exhibitor")
            appearances.append({"account_id": acct["id"], "event_id": event["id"], "role": c.get("role_at_event"),
                                "tier": c.get("tier"), "category": c.get("category"), "source_url": c.get("source_url"),
                                "edition": c.get("edition")})

    a_cfg = cfg["account"]
    account_rows = []
    for acct in accounts.values():
        profile = acct["profile"]
        c_pts, c_reasons, c_tags = score_company(profile, cfg)
        reasons = [dict(r, points=round(r["points"] * a_cfg["company_multiplier"])) for r in c_reasons]
        ev_pts = min(a_cfg["max_event_points"], a_cfg["per_event_points"] * len(acct["events"]))
        reasons.append({"label": f"At {len(acct['events'])} target event{'s' if len(acct['events']) != 1 else ''}", "points": ev_pts, "kind": "event"})
        if acct["contacts"]:
            reasons.append({"label": f"{len(acct['contacts'])} named contact{'s' if len(acct['contacts']) != 1 else ''} at events", "points": a_cfg["named_contact_points"], "kind": "event"})
            if max(c["role_fit"] for c in acct["contacts"]) >= a_cfg["target_contact_role_min"]:
                reasons.append({"label": "Has a contact in a target role", "points": a_cfg["target_contact_points"], "kind": "role"})
        score = min(100, sum(r["points"] for r in reasons))
        confidence = (profile or {}).get("confidence", "low") if profile else "low"
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"
        row = {
            "id": acct["id"], "name": acct["name"], "score": score, "reasons": reasons, "tags": c_tags,
            "events": sorted(acct["events"], key=lambda e: events[e]["start"]), "roles": sorted(acct["roles"]),
            "contact_ids": [c["id"] for c in acct["contacts"]], "confidence": confidence,
            "profile": profile or {}, "estimated": True,
        }
        row["lane"] = lane_for(profile, score, confidence, cfg)
        account_rows.append(row)

    if have_sources:
        with open(checks_path, "w", encoding="utf-8") as f:
            json.dump(checks, f, indent=0, sort_keys=True)
    return events, contacts, account_rows, appearances


def build(today=None, con=None):
    """Rebuild leads and scores with the active scoring version. Decisions and versions are kept."""
    today = today or dt.date.today()
    own = con is None
    con = con or connect()
    sync_repo_configs(con)
    cfg, version = active_scoring(con)
    events, contacts, account_rows, appearances = compute(cfg, today)
    con.executescript(LEAD_TABLES)
    con.executemany("INSERT INTO events VALUES (?, ?)", [(e["id"], json.dumps(e, ensure_ascii=False)) for e in events.values()])
    con.executemany("INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?)",
                    [(c["id"], c["account_id"], c["event_id"], c["score"], c["lane"], json.dumps(c, ensure_ascii=False)) for c in contacts])
    con.executemany("INSERT INTO accounts VALUES (?, ?, ?, ?)",
                    [(a["id"], a["score"], a["lane"], json.dumps(a, ensure_ascii=False)) for a in account_rows])
    con.executemany("INSERT INTO appearances VALUES (?, ?, ?, ?)",
                    [(a["account_id"], a["event_id"], a["role"], json.dumps(a, ensure_ascii=False)) for a in appearances])
    meta = {"built_at": dt.datetime.now().isoformat(timespec="minutes"), "today": today.isoformat(),
            "lanes": cfg["lanes"], "scoring_version": version}
    con.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in meta.items()])
    lanes = {}
    for c in contacts:
        lanes[c["lane"]] = lanes.get(c["lane"], 0) + 1
    summary = {"contacts": len(contacts), "accounts": len(account_rows), "lanes": lanes, "scoring_version": version}
    con.execute("INSERT INTO events_log (kind, message, data, created_at) VALUES ('build', ?, ?, ?)",
                (f"Rebuilt with scoring v{version}: {len(contacts)} contacts, {len(account_rows)} accounts", json.dumps(summary), now()))
    con.commit()
    if own:
        con.close()
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=dt.date.today().isoformat())
    print(build(dt.date.fromisoformat(ap.parse_args().today)))
