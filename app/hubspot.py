"""Push approved leads to HubSpot: companies and contacts, linked, without duplicates.

Every record carries our own stable id (gm_account_id / gm_lead_id), so a lead pushed twice
updates the same HubSpot record, even if the local sync table were lost. Records HubSpot had before the cockpit
(a company by domain or name, a person by name at the same company) are used rather than duplicated.
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

    def search(self, obj, filters, props):
        """Every record matching all `filters` (up to 1,000), with only the properties we read."""
        out, after = [], None
        for _ in range(5):
            r = self.request("POST", f"/crm/v3/objects/{obj}/search", json={
                "filterGroups": [{"filters": filters}], "properties": props, "limit": 200} | ({"after": after} if after else {}))
            page = r.json() if r.status_code == 200 else {}
            out += page.get("results", [])
            after = ((page.get("paging") or {}).get("next") or {}).get("after")
            if not after:
                break
        return out

    def owners(self):
        """Owner names by id, or nothing if the key may not read owners (the page then shows the id)."""
        try:
            r = self.request("GET", "/crm/v3/owners", params={"limit": 500})
        except HubSpotError:
            return {}
        rows = r.json().get("results", []) if r.status_code == 200 else []
        return {str(o["id"]): " ".join(filter(None, (o.get("firstName"), o.get("lastName")))) or o.get("email") for o in rows}

    def lookup(self, accounts, people):
        """Read-only: what HubSpot already has, whoever created it. A company is found by its domain, else by its exact name;
        a person by first and last name, kept only if their company in HubSpot is ours (the same record, or the same name).
        Returns {"companies": {account id: record}, "contacts": {person key: record}}; a record is its HubSpot id, lifecycle
        stage, owner, the company it's linked to and whether it carries our id. A few requests for a whole event."""
        low = lambda s: (s or "").strip().lower()  # HubSpot's IN filter wants lowercase values
        chunks = lambda xs: [xs[i:i + 50] for i in range(0, len(xs), 50)]
        best = lambda hits, prop, ours: min(hits, key=lambda r: (r["properties"].get(prop) != ours, int(r["id"])), default=None)

        cprops = ["name", "domain", "lifecyclestage", "hubspot_owner_id", "gm_account_id"]
        found = {}
        for field, key in (("domain", lambda a: low((a.get("profile") or {}).get("domain"))), ("name", lambda a: low(a.get("name")))):
            todo = [a for a in accounts if a["id"] not in found and key(a)]  # by name only where the domain found nothing
            values = sorted({key(a) for a in todo})
            hits = [r for chunk in chunks(values) for r in self.search("companies", [{"propertyName": field, "operator": "IN", "values": chunk}], cprops)]
            for a in todo:
                match = best([r for r in hits if low(r["properties"].get(field)) == key(a)], "gm_account_id", a["id"])
                if match:
                    found[a["id"]] = match

        pprops = ["firstname", "lastname", "company", "associatedcompanyid", "lifecyclestage", "hubspot_owner_id", "gm_lead_id"]
        named = [p for p in people if p.get("first_name") and p.get("last_name")]
        hits = [r for chunk in chunks(named) for r in self.search("contacts", [
            {"propertyName": "firstname", "operator": "IN", "values": sorted({low(p["first_name"]) for p in chunk})},
            {"propertyName": "lastname", "operator": "IN", "values": sorted({low(p["last_name"]) for p in chunk})}], pprops)]
        by_id = {a["id"]: a for a in accounts}
        contacts = {}
        for p in named:
            acct = by_id.get(p.get("account_id")) or {}
            ours = {low(acct.get("name")), low(p.get("company"))} - {""}
            company_id = found.get(acct.get("id"), {}).get("id")
            same = lambda q: (company_id and q.get("associatedcompanyid") == company_id) or low(q.get("company")) in ours
            match = best([r for r in hits if low(r["properties"].get("firstname")) == low(p["first_name"])
                          and low(r["properties"].get("lastname")) == low(p["last_name"]) and same(r["properties"])], "gm_lead_id", p["person_key"])
            if match:
                contacts[p["person_key"]] = match

        records = list(found.values()) + list(contacts.values())
        names = self.owners() if any(r["properties"].get("hubspot_owner_id") for r in records) else {}
        record = lambda r, prop, ours: {
            "id": r["id"], "stage": r["properties"].get("lifecyclestage"), "ours": r["properties"].get(prop) == ours,
            "owner": names.get(r["properties"].get("hubspot_owner_id")) or r["properties"].get("hubspot_owner_id"),
            "company_id": r["properties"].get("associatedcompanyid")}
        return {"companies": {a: record(r, "gm_account_id", a) for a, r in found.items()},
                "contacts": {k: record(r, "gm_lead_id", k) for k, r in contacts.items()}}

    def upsert(self, obj, known_id, id_prop, id_value, props, existing=None, on_create=None):
        """Update the record we know, else the one carrying our id, else one HubSpot already had (`existing`, from the
        lookup), else create it. Returns the id and "updated", "linked" (HubSpot had it before the cockpit) or "created".
        An existing record only gets `props` (our GM fields); `on_create` (name, title, lifecycle stage) is sent only when
        we create it, so what sales has corrected, a customer's own record, its owner and its stage are never overwritten."""
        hid = known_id
        if hid and self.request("GET", f"/crm/v3/objects/{obj}/{hid}").status_code == 404:
            hid = None
        hid = hid or self.find(obj, id_prop, id_value)
        how = "updated" if hid else "linked" if existing else "created"
        hid = hid or existing
        if hid:
            self.request("PATCH", f"/crm/v3/objects/{obj}/{hid}", json={"properties": props})
            return hid, how
        r = self.request("POST", f"/crm/v3/objects/{obj}", json={"properties": props | (on_create or {})})
        return r.json()["id"], how

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


def source_event(contact, event):
    """e.g. "Speaker at BME-eLÖSUNGSTAGE 2027 (2027-05-11), from the 2026 edition's list": last year's names aren't confirmed attendees."""
    text = f"{event['name']} ({event['start']})"
    if event["id"] != contact["event_id"]:
        return text
    role, edition = contact.get("role_at_event"), contact.get("edition") or ""
    text = f"{role.capitalize()} at {text}" if role else text
    return text + (f", from the {edition.split()[0]} edition's list" if "previous" in edition else "")


STANDARD = {"companies": ("name", "domain", "country"), "contacts": ("firstname", "lastname", "jobtitle", "company")}


def split(obj, props):
    """Our GM fields (always sent) and HubSpot's standard fields (sent only when we create the record)."""
    std = {k: v for k, v in props.items() if k in STANDARD[obj]}
    return {k: v for k, v in props.items() if k not in std}, std


def contact_props(contact, account, events):
    evs = [events[e] for e in contact.get("approved_events") or [contact["event_id"]] if e in events]
    props = {
        "firstname": contact["first_name"], "lastname": contact["last_name"], "jobtitle": contact.get("title") or "",
        "company": (account or {}).get("name") or contact.get("company") or "", "gm_lead_id": contact["person_key"],
        "gm_fit_score": contact["score"], "gm_fit_reasons": reasons_text(contact["reasons"]),
        "gm_source_event": " | ".join(source_event(contact, e) for e in evs), "gm_source_url": contact.get("source_url") or "",
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
    try:  # records HubSpot already had are used, not duplicated; if it can't be asked, the send carries on without
        found = hs.lookup(approved_accounts, approved_contacts)
    except (HubSpotError, httpx.HTTPError) as e:
        found, summary["lookup_error"] = None, str(e)[:200]
    existing = lambda kind, oid: (found[kind].get(oid) or {}) if found else {}

    def save(kind, oid, hid):
        con.execute("INSERT OR REPLACE INTO hubspot_sync VALUES (?, ?, ?, ?)", (kind, oid, hid, synced_at))
        con.commit()  # short write locks, so reviewers can keep deciding while a push runs
        known[(kind, oid)] = hid

    def push_account(acct):
        if ("account", acct["id"]) in pushed:
            return known.get(("account", acct["id"]))
        domain = (acct.get("profile") or {}).get("domain")
        gm, std = split("companies", company_props(acct, events))
        had = existing("companies", acct["id"]).get("id")
        if found is None and not known.get(("account", acct["id"])):  # HubSpot couldn't be asked: at least match the domain
            had = hs.find("companies", "domain", domain)
        hid, how = hs.upsert("companies", known.get(("account", acct["id"])), "gm_account_id", acct["id"], gm, existing=had, on_create=std)
        save("account", acct["id"], hid)
        if how == "created":  # remember which companies the cockpit created, so only those can ever be removed again
            save("account_created", acct["id"], hid)
        pushed.add(("account", acct["id"]))
        summary["companies_created" if how == "created" else "companies_updated"] += 1
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
            gm, std = split("contacts", contact_props(c, acct, events))
            had = existing("contacts", c["person_key"])
            hid, how = hs.upsert("contacts", known.get(("contact", c["person_key"])), "gm_lead_id", c["person_key"], gm,
                                 existing=had.get("id"), on_create=std | {"lifecyclestage": "lead"})
            save("contact", c["person_key"], hid)
            if how == "linked":  # HubSpot had them before the cockpit: Remove from HubSpot must never delete them
                save("contact_linked", c["person_key"], hid)
            for listing in c.get("approved_ids") or [c["id"]]:  # each event listing sent, so the cockpit can show it as "In HubSpot"
                save("listing", listing, hid)
            summary["contacts_created" if how == "created" else "contacts_updated"] += 1
            if company_id and not (how == "linked" and had.get("company_id")):  # a contact HubSpot had keeps its own company
                hs.associate(hid, company_id)
        except HubSpotError as e:
            summary["errors"].append(f"{c['name']}: {e}")
    summary["errors"] = summary["errors"][:20]
    return summary


_status_cache = {"at": 0, "value": None}


def reset_status():
    _status_cache.update(at=0, value=None)


def status(fresh=False):
    """Connection health, cached for a minute so the page can show a live light without hammering the API."""
    if not token():
        return {"configured": False, "ok": False, "message": "No HubSpot token configured"}
    if not fresh and time.time() - _status_cache["at"] < 60 and _status_cache["value"]:
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
    """Take one person (all their event listings) out of HubSpot. Their company goes too only if the cockpit
    created it and nobody else the cockpit sent works there."""
    hs = Client()
    known = {(r["object_type"], r["object_id"]): r["hubspot_id"] for r in con.execute("SELECT * FROM hubspot_sync")}
    out = {}
    hid = known.get(("contact", person_key))
    if hid and known.get(("contact_linked", person_key)) == hid:  # the marker stays, so a later send can't make it ours
        out["contact"] = "kept (it was in HubSpot before the cockpit)"
    elif hid:
        out["contact"] = hs.archive("contacts", hid, "gm_lead_id", person_key)
    con.execute("DELETE FROM hubspot_sync WHERE object_type = 'contact' AND object_id = ?", (person_key,))
    listings = [r["id"] for r in con.execute("SELECT id FROM contacts WHERE json_extract(data, '$.person_key') = ?", (person_key,))]
    con.executemany("DELETE FROM hubspot_sync WHERE object_type = 'listing' AND object_id = ?", [(i,) for i in listings])
    con.commit()  # the person is out on both sides before the company step starts
    company = known.get(("account", account_id)) if account_id else None
    if company:
        others = con.execute(
            "SELECT 1 FROM hubspot_sync s JOIN contacts c ON s.object_type = 'contact' AND s.object_id = json_extract(c.data, '$.person_key') "
            "WHERE c.account_id = ? LIMIT 1", (account_id,)).fetchone()
        shared = sum(1 for (kind, _), h in known.items() if kind == "account" and h == company) > 1
        if others or shared:
            out["company"] = "kept (others from it are in HubSpot)"
        elif known.get(("account_created", account_id)) != company:
            out["company"] = "kept (it was in HubSpot before the cockpit)"
            con.execute("DELETE FROM hubspot_sync WHERE object_type = 'account' AND object_id = ?", (account_id,))
        else:
            try:
                out["company"] = hs.archive("companies", company, "gm_account_id", account_id)
                con.execute("DELETE FROM hubspot_sync WHERE object_type IN ('account', 'account_created') AND object_id = ?", (account_id,))
            except (HubSpotError, httpx.HTTPError) as e:
                out["company"] = f"kept: {str(e)[:120]}"
        con.commit()
    return out
