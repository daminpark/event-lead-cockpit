"""Push approved leads to HubSpot: companies and contacts, linked, without duplicates.

Every record carries our own stable id (gm_account_id / gm_lead_id), so a lead pushed twice
updates the same HubSpot record, even if the local sync table were lost.
"""

import json
import os
import time

import httpx

API = "https://api.hubapi.com"
TIMEOUT = httpx.Timeout(20.0)

COMPANY_PROPS = [
    ("gm_account_id", "GM account id", "string", "text"),
    ("gm_fit_score", "GM fit score", "number", "number"),
    ("gm_fit_reasons", "GM fit reasons", "string", "textarea"),
    ("gm_segment", "GM segment", "string", "text"),
    ("gm_source_events", "GM source events", "string", "textarea"),
]
CONTACT_PROPS = [
    ("gm_lead_id", "GM lead id", "string", "text"),
    ("gm_fit_score", "GM fit score", "number", "number"),
    ("gm_fit_reasons", "GM fit reasons", "string", "textarea"),
    ("gm_source_event", "GM source event", "string", "text"),
    ("gm_source_url", "GM source URL", "string", "text"),
    ("gm_session", "GM session at event", "string", "textarea"),
]


class HubSpotError(Exception):
    pass


def token():
    from app import secrets_store
    return secrets_store.get("hubspot")


class Client:
    def __init__(self):
        if not token():
            raise HubSpotError("No HUBSPOT_TOKEN configured")
        self.http = httpx.Client(base_url=API, timeout=TIMEOUT, headers={"Authorization": f"Bearer {token()}"})

    def request(self, method, path, **kw):
        for attempt in range(4):
            r = self.http.request(method, path, **kw)
            if r.status_code == 429:  # free tier: about 100 requests per 10 seconds
                time.sleep(float(r.headers.get("Retry-After", 2)) + attempt)
                continue
            if r.status_code >= 400 and r.status_code != 404:
                raise HubSpotError(f"{method} {path}: {r.status_code} {r.text[:300]}")
            return r
        raise HubSpotError(f"{method} {path}: rate limited")

    def account(self):
        """Portal id and the UI domain (EU accounts live on app-eu1.hubspot.com)."""
        r = self.request("GET", "/account-info/v3/details")
        d = r.json() if r.status_code == 200 else {}
        return d.get("portalId"), d.get("uiDomain") or "app.hubspot.com"

    def health(self):
        r = self.request("GET", "/crm/v3/objects/companies", params={"limit": 1})
        return r.status_code == 200

    def ensure_properties(self):
        created = []
        for obj, props, group in (("companies", COMPANY_PROPS, "companyinformation"), ("contacts", CONTACT_PROPS, "contactinformation")):
            for name, label, kind, field in props:
                if self.request("GET", f"/crm/v3/properties/{obj}/{name}").status_code == 200:
                    continue
                self.request("POST", f"/crm/v3/properties/{obj}", json={
                    "name": name, "label": label, "type": kind, "fieldType": field, "groupName": group,
                    "description": "Set by the event lead cockpit",
                })
                created.append(f"{obj}.{name}")
        return created

    def find(self, obj, prop, value):
        if not value:
            return None
        r = self.request("POST", f"/crm/v3/objects/{obj}/search", json={
            "filterGroups": [{"filters": [{"propertyName": prop, "operator": "EQ", "value": value}]}], "limit": 1,
        })
        results = r.json().get("results", []) if r.status_code == 200 else []
        return results[0]["id"] if results else None

    def upsert(self, obj, known_id, id_prop, id_value, props, fallback=None):
        """Update the record we know, else find it by our id (or a fallback like domain), else create it."""
        hid = known_id
        if hid and self.request("GET", f"/crm/v3/objects/{obj}/{hid}").status_code == 404:
            hid = None
        hid = hid or self.find(obj, id_prop, id_value) or (self.find(obj, *fallback) if fallback else None)
        if hid:
            self.request("PATCH", f"/crm/v3/objects/{obj}/{hid}", json={"properties": props})
            return hid, False
        r = self.request("POST", f"/crm/v3/objects/{obj}", json={"properties": props})
        return r.json()["id"], True

    def archive(self, obj, hid, id_prop, expected):
        """Move a record to HubSpot's recycle bin (restorable for 90 days), but only if it carries our id."""
        r = self.request("GET", f"/crm/v3/objects/{obj}/{hid}", params={"properties": id_prop})
        if r.status_code == 404:
            return "already gone"
        found = (r.json().get("properties") or {}).get(id_prop)
        if found != expected:
            raise HubSpotError(f"{obj} {hid} carries {id_prop}={found!r}, not {expected!r}: left untouched")
        self.request("DELETE", f"/crm/v3/objects/{obj}/{hid}")
        return "moved to recycle bin"

    def associate(self, contact_id, company_id):
        self.request("PUT", f"/crm/v4/objects/contacts/{contact_id}/associations/default/companies/{company_id}")


def reasons_text(reasons):
    return "; ".join(f"{r['label']} (+{r['points']})" for r in reasons if r["points"])[:2000]


def company_props(account, events):
    p = account.get("profile") or {}
    props = {
        "name": account["name"], "gm_account_id": account["id"], "gm_fit_score": account["score"],
        "gm_fit_reasons": reasons_text(account["reasons"]), "gm_segment": p.get("segment") or "",
        "gm_source_events": " | ".join(events[e]["name"] for e in account["events"] if e in events),
    }
    if p.get("domain"):
        props["domain"] = p["domain"]
    if p.get("hq_country"):
        props["country"] = p["hq_country"]
    return props


def contact_props(contact, account, events):
    evs = [events[e] for e in contact.get("approved_events") or [contact["event_id"]] if e in events]
    props = {
        "firstname": contact["first_name"], "lastname": contact["last_name"], "jobtitle": contact.get("title") or "",
        "company": (account or {}).get("name") or contact.get("company") or "", "gm_lead_id": contact["person_key"],
        "gm_fit_score": contact["score"], "gm_fit_reasons": reasons_text(contact["reasons"]),
        "gm_source_event": " | ".join(f"{e['name']} ({e['start']})" for e in evs), "gm_source_url": contact.get("source_url") or "",
        "gm_session": contact.get("session") or "",
    }
    return props


def push(con, approved_accounts, approved_contacts, accounts_by_id, events, synced_at):
    """Push everything approved. Returns a summary; raises HubSpotError if HubSpot can't be reached."""
    hs = Client()
    created_props = hs.ensure_properties()
    known = {(r["object_type"], r["object_id"]): r["hubspot_id"] for r in con.execute("SELECT * FROM hubspot_sync")}
    summary = {"companies_created": 0, "companies_updated": 0, "contacts_created": 0, "contacts_updated": 0,
               "properties_created": created_props, "errors": []}

    def save(kind, oid, hid):
        con.execute("INSERT OR REPLACE INTO hubspot_sync VALUES (?, ?, ?, ?)", (kind, oid, hid, synced_at))
        con.commit()  # short write locks, so reviewers can keep deciding while a push runs
        known[(kind, oid)] = hid

    def push_account(acct):
        if ("account", acct["id"]) in pushed:
            return known.get(("account", acct["id"]))
        domain = (acct.get("profile") or {}).get("domain")
        hid, new = hs.upsert("companies", known.get(("account", acct["id"])), "gm_account_id", acct["id"],
                             company_props(acct, events), fallback=("domain", domain) if domain else None)
        save("account", acct["id"], hid)
        pushed.add(("account", acct["id"]))
        summary["companies_created" if new else "companies_updated"] += 1
        return hid

    pushed = set()
    for acct in approved_accounts:
        try:
            push_account(acct)
        except HubSpotError as e:
            summary["errors"].append(f"{acct['name']}: {e}")
    for c in approved_contacts:
        try:
            acct = accounts_by_id.get(c["account_id"])
            company_id = push_account(acct) if acct else None
            hid, new = hs.upsert("contacts", known.get(("contact", c["person_key"])), "gm_lead_id", c["person_key"], contact_props(c, acct, events))
            save("contact", c["person_key"], hid)
            for listing in c.get("approved_ids") or [c["id"]]:  # each event listing sent, so the cockpit can show it as "In HubSpot"
                save("listing", listing, hid)
            summary["contacts_created" if new else "contacts_updated"] += 1
            if company_id:
                hs.associate(hid, company_id)
        except HubSpotError as e:
            summary["errors"].append(f"{c['name']}: {e}")
    summary["errors"] = summary["errors"][:20]
    return summary


_status_cache = {"at": 0, "value": None}


def reset_status():
    _status_cache.update(at=0, value=None)


def status():
    """Connection health, cached for a minute so the page can show a live light without hammering the API."""
    if not token():
        return {"configured": False, "ok": False, "message": "No HubSpot token configured"}
    if time.time() - _status_cache["at"] < 60 and _status_cache["value"]:
        return _status_cache["value"]
    try:
        hs = Client()
        ok = hs.health()
        portal, ui = hs.account()
        value = {"configured": True, "ok": ok, "portal_id": portal, "ui_domain": ui, "message": "Connected" if ok else "HubSpot refused the key"}
    except (HubSpotError, httpx.HTTPError) as e:
        value = {"configured": True, "ok": False, "message": str(e)[:200]}
    _status_cache.update(at=time.time(), value=value)
    return value


def record_url(portal_id, kind, hid, ui_domain="app.hubspot.com"):
    if not portal_id or not hid:
        return None
    return f"https://{ui_domain}/contacts/{portal_id}/record/{'0-2' if kind == 'account' else '0-1'}/{hid}"


def dumps(v):
    return json.dumps(v, ensure_ascii=False)


def remove_person(con, person_key, account_id):
    """Take one person (all their event listings) out of HubSpot, and their company if nobody else from it is there."""
    hs = Client()
    known = {(r["object_type"], r["object_id"]): r["hubspot_id"] for r in con.execute("SELECT * FROM hubspot_sync")}
    out = {}
    hid = known.get(("contact", person_key))
    if hid:
        out["contact"] = hs.archive("contacts", hid, "gm_lead_id", person_key)
    con.execute("DELETE FROM hubspot_sync WHERE object_type = 'contact' AND object_id = ?", (person_key,))
    listings = [r["id"] for r in con.execute("SELECT id FROM contacts WHERE json_extract(data, '$.person_key') = ?", (person_key,))]
    con.executemany("DELETE FROM hubspot_sync WHERE object_type = 'listing' AND object_id = ?", [(i,) for i in listings])
    if account_id and ("account", account_id) in known:
        # keep the company if another person from it is still in HubSpot
        others = con.execute(
            "SELECT 1 FROM hubspot_sync s JOIN contacts c ON s.object_type = 'listing' AND s.object_id = c.id WHERE c.account_id = ? LIMIT 1",
            (account_id,)).fetchone()
        if not others:
            out["company"] = hs.archive("companies", known[("account", account_id)], "gm_account_id", account_id)
            con.execute("DELETE FROM hubspot_sync WHERE object_type = 'account' AND object_id = ?", (account_id,))
    con.commit()
    return out
