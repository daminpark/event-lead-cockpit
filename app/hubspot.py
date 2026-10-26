"""Push approved leads to HubSpot: companies and contacts, linked, without duplicates.

Every record carries our own stable id (gm_account_id / gm_lead_id), so a lead pushed twice
updates the same HubSpot record, even if the local sync table were lost. A record HubSpot had before the cockpit is used
only when it's surely the same (a company by its domain, a person by name at the same company); when it only might be, nothing
is linked or created until a person confirms it.
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


class NotSent(Exception):
    """A record the send leaves for later, with the reason: it can't be sure what HubSpot already has."""


UNCHECKED = "Not sent, couldn't check HubSpot for an existing record (send again later)"
POSSIBLE = "Not sent, possible match in HubSpot (someone needs to confirm it)"
NAMESAKE = "Not sent, same name as a contact HubSpot already had at another company (someone needs to confirm it's the same person)"
CPROPS = ["name", "domain", "lifecyclestage", "hubspot_owner_id", "gm_account_id"]
low = lambda s: (s or "").strip().lower()  # HubSpot's IN filter wants lowercase values
domain_of = lambda a: low((a.get("profile") or {}).get("domain"))


def company_match(account, hits, field):
    """Of the HubSpot companies with this account's domain (or name), the one that is surely ours, else one that only might be.
    Surely ours: it carries our id, or it has our domain and no other cockpit account's id. Anything else (the same name with
    another or no domain, or another account's record) is a possible match: never linked silently, a person confirms it
    (an AI will later suggest whether they're the same)."""
    value = domain_of(account) if field == "domain" else low(account.get("name"))
    gm = lambda r: r["properties"].get("gm_account_id")
    same = sorted((r for r in hits if low(r["properties"].get(field)) == value), key=lambda r: (gm(r) != account["id"], int(r["id"])))
    sure = [r for r in same if gm(r) == account["id"] or (field == "domain" and not gm(r))]
    return (sure[0], None) if sure else (None, same[0] if same else None)


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
        """Every record matching all `filters`, with only the properties we read. Never a partial list: past 1,000 matches
        it raises, so nothing is decided on half an answer."""
        out, after = [], None
        for _ in range(5):
            r = self.request("POST", f"/crm/v3/objects/{obj}/search", json={
                "filterGroups": [{"filters": filters}], "properties": props, "limit": 200} | ({"after": after} if after else {}))
            page = r.json() if r.status_code == 200 else {}
            out += page.get("results", [])
            after = ((page.get("paging") or {}).get("next") or {}).get("after")
            if not after:
                return out
        raise HubSpotError(f"too many {obj} with these names to check")

    def owners(self):
        """Owner names by id, or nothing if the key may not read owners (the page then shows the id)."""
        try:
            r = self.request("GET", "/crm/v3/owners", params={"limit": 500})
        except HubSpotError:
            return {}
        rows = r.json().get("results", []) if r.status_code == 200 else []
        return {str(o["id"]): " ".join(filter(None, (o.get("firstName"), o.get("lastName")))) or o.get("email") for o in rows}

    def lookup(self, accounts, people):
        """Read-only: what HubSpot already has, whoever created it. Companies by domain, then by exact name (see company_match).
        A person by first and last name, kept only at one of the companies of their approved listings: the same HubSpot company,
        or its name. `accounts` must include all those companies. Raises HubSpotError rather than answer in part.
        Returns {"companies": {account id: record}, "possible": {account id: record}, "contacts": {person key: record}};
        a record is the HubSpot id, lifecycle stage and owner (a possible company also its name and domain)."""
        chunks = lambda xs, n: [xs[i:i + n] for i in range(0, len(xs), n)]
        sure, possible = {}, {}
        for field, key in (("domain", domain_of), ("name", lambda a: low(a.get("name")))):
            seen = sure | possible
            todo = [a for a in accounts if a["id"] not in seen and key(a)]  # by name only where the domain found nothing
            values = sorted({key(a) for a in todo})
            hits = [r for chunk in chunks(values, 50) for r in self.search("companies", [{"propertyName": field, "operator": "IN", "values": chunk}], CPROPS)]
            for a in todo:
                match, maybe = company_match(a, hits, field)
                if match:
                    sure[a["id"]] = match
                elif maybe:
                    possible[a["id"]] = maybe

        pprops = ["firstname", "lastname", "company", "associatedcompanyid", "lifecyclestage", "hubspot_owner_id", "gm_lead_id"]
        named = [p for p in people if p.get("first_name") and p.get("last_name")]
        hits = [r for chunk in chunks(named, 10) for r in self.search("contacts", [  # small chunks, so first names x last names stays small
            {"propertyName": "firstname", "operator": "IN", "values": sorted({low(p["first_name"]) for p in chunk})},
            {"propertyName": "lastname", "operator": "IN", "values": sorted({low(p["last_name"]) for p in chunk})}], pprops)]
        by_id = {a["id"]: a for a in accounts}
        contacts = {}
        for p in named:
            listings = p.get("approved_companies") or [(p.get("account_id"), p.get("company"))]
            ids = {sure[a]["id"] for a, _ in listings if a in sure}
            names = ({low((by_id.get(a) or {}).get("name")) for a, _ in listings} | {low(t) for _, t in listings}) - {""}
            same = [r for r in hits if (low(r["properties"].get("firstname")), low(r["properties"].get("lastname"))) == (low(p["first_name"]), low(p["last_name"]))
                    and (r["properties"].get("associatedcompanyid") in ids or low(r["properties"].get("company")) in names)]
            if same:
                contacts[p["person_key"]] = min(same, key=lambda r: (r["properties"].get("gm_lead_id") != p["person_key"], int(r["id"])))

        records = [*sure.values(), *possible.values(), *contacts.values()]
        owners = self.owners() if any(r["properties"].get("hubspot_owner_id") for r in records) else {}

        def record(r, **more):
            p = r["properties"]
            return {"id": r["id"], "stage": p.get("lifecyclestage"), "owner": owners.get(p.get("hubspot_owner_id")) or p.get("hubspot_owner_id")} | {k: p.get(v) for k, v in more.items()}
        return {"companies": {a: record(r) for a, r in sure.items()},
                "possible": {a: record(r, name="name", domain="domain") for a, r in possible.items()},
                "contacts": {k: record(r, company_id="associatedcompanyid") for k, r in contacts.items()}}

    def ours(self, obj, known_id, id_prop, id_value):
        """The record we sent before, if it's still there, else the one carrying our id."""
        if known_id and self.request("GET", f"/crm/v3/objects/{obj}/{known_id}").status_code != 404:
            return known_id
        return self.find(obj, id_prop, id_value)

    def write(self, obj, hid, props, on_create):
        """Only our GM fields onto a record HubSpot has; a new record also gets `on_create` (name, title, lifecycle stage).
        So what sales has corrected, a customer's own record, its owner and its stage are never overwritten."""
        if hid:
            self.request("PATCH", f"/crm/v3/objects/{obj}/{hid}", json={"properties": props})
            return hid
        return self.request("POST", f"/crm/v3/objects/{obj}", json={"properties": props | on_create}).json()["id"]

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
    """Push everything approved. Returns a summary; raises HubSpotError if HubSpot can't be reached.
    What the cockpit sent before is updated. A record HubSpot already had is used only when the lookup is sure it's the same;
    a new one is created only when the lookup could look. Anything else stays unsent, with the reason, for a later send."""
    hs = Client()
    created_props = hs.ensure_properties()
    known = {(r["object_type"], r["object_id"]): r["hubspot_id"] for r in con.execute("SELECT * FROM hubspot_sync")}
    summary = {"companies_created": 0, "companies_updated": 0, "contacts_created": 0, "contacts_updated": 0,
               "properties_created": created_props, "not_sent": {}, "errors": []}
    listed = {a for c in approved_contacts for a, _ in c.get("approved_companies") or []} - {a["id"] for a in approved_accounts}
    try:  # a person is recognised at the companies of all their listings, so those are looked up too
        found = hs.lookup(approved_accounts + [accounts_by_id[a] for a in listed if a in accounts_by_id], approved_contacts)
    except (HubSpotError, httpx.HTTPError) as e:
        found, summary["lookup_error"] = None, str(e)[:200]

    def save(kind, oid, hid):
        con.execute("INSERT OR REPLACE INTO hubspot_sync VALUES (?, ?, ?, ?)", (kind, oid, hid, synced_at))
        con.commit()  # short write locks, so reviewers can keep deciding while a push runs
        known[(kind, oid)] = hid

    def send_account(acct):
        aid, domain = acct["id"], (acct.get("profile") or {}).get("domain")
        hid, how = hs.ours("companies", known.get(("account", aid)), "gm_account_id", aid), "updated"
        if not hid:
            match, maybe = (found["companies"].get(aid), found["possible"].get(aid)) if found else (None, None)
            if not match and domain:  # the lookup missed it or couldn't run: ask for the domain exactly, as before
                match, also = company_match(acct, hs.search("companies", [{"propertyName": "domain", "operator": "EQ", "value": domain}], CPROPS), "domain")
                maybe = maybe or also
            if not match and (maybe or found is None):
                raise NotSent(POSSIBLE if maybe else UNCHECKED)
            hid, how = (match["id"], "linked") if match else (None, "created")
        gm, std = split("companies", company_props(acct, events))
        hid = hs.write("companies", hid, gm, std)
        save("account", aid, hid)
        if how == "created":  # remember which companies the cockpit created, so only those can ever be removed again
            save("account_created", aid, hid)
        summary["companies_created" if how == "created" else "companies_updated"] += 1
        return hid

    done = {}  # account id -> its HubSpot id, or why it isn't sent

    def push_account(acct):
        if acct["id"] not in done:
            try:
                done[acct["id"]] = send_account(acct)
            except NotSent as e:
                done[acct["id"]] = e
        if isinstance(done[acct["id"]], NotSent):
            raise done[acct["id"]]  # its people wait with it
        return done[acct["id"]]

    def not_sent(why, name):
        summary["not_sent"].setdefault(why, []).append(name)

    for acct in approved_accounts:
        try:
            push_account(acct)
        except NotSent as e:
            not_sent(str(e), acct["name"])
        except HubSpotError as e:
            summary["errors"].append(f"{acct['name']}: {e}")
    for c in approved_contacts:
        try:
            acct, key = accounts_by_id.get(c["account_id"]), c["person_key"]
            company_id = push_account(acct) if acct else None
            had = (found["contacts"].get(key) if found else None) or {}
            hid = hs.ours("contacts", known.get(("contact", key)), "gm_lead_id", key)
            if hid and hid == known.get(("contact_linked", key)) and had.get("id") != hid:  # HubSpot's own record, not at their companies this time
                raise NotSent(UNCHECKED if found is None else NAMESAKE)
            if not hid and not had and found is None:
                raise NotSent(UNCHECKED)
            how = "updated" if hid else "linked" if had else "created"
            gm, std = split("contacts", contact_props(c, acct, events))
            hid = hs.write("contacts", hid or had.get("id"), gm, std | {"lifecyclestage": "lead"})
            save("contact", key, hid)
            if how == "linked":  # HubSpot had them before the cockpit: Remove from HubSpot must never delete them
                save("contact_linked", key, hid)
            for listing in c.get("approved_ids") or [c["id"]]:  # each event listing sent, so the cockpit can show it as "In HubSpot"
                save("listing", listing, hid)
            summary["contacts_created" if how == "created" else "contacts_updated"] += 1
            if company_id and (how == "created" or (how == "linked" and not had.get("company_id"))):  # a contact HubSpot had keeps its own company
                hs.associate(hid, company_id)
        except NotSent as e:
            not_sent(str(e), c["name"])
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
