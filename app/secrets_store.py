"""API keys for HubSpot and OpenRouter: pasted in the cockpit's Settings (owner only), else from the server environment.

Values are stored on the server and never sent back to the browser; the page only learns whether a key is set
and its last four characters.
"""

import os
import time
from contextlib import closing

import httpx

from pipeline import build as pipeline

ENV = {"hubspot": "HUBSPOT_TOKEN", "openrouter": "OPENROUTER_API_KEY"}
PREFIX = {"hubspot": "pat-", "openrouter": "sk-or-"}
_cache = {}


def _stored(name):
    with closing(pipeline.connect(pipeline.DB)) as con:
        row = con.execute("SELECT value FROM settings WHERE key = ?", (f"secret:{name}",)).fetchone()
    return row["value"] if row else ""


def get(name):
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    value = _stored(name) or os.environ.get(ENV[name], "").strip()
    _cache[name] = (time.time(), value)
    return value


def status(name):
    stored = _stored(name)
    value = stored or os.environ.get(ENV[name], "").strip()
    return {"set": bool(value), "source": "cockpit" if stored else "server" if value else None,
            "hint": f"…{value[-4:]}" if len(value) > 8 else None}


def check(name, value):
    """Ask the service itself whether a key works. Returns (ok, detail)."""
    try:
        if name == "openrouter":
            for path in ("/api/v1/key", "/api/v1/auth/key"):
                r = httpx.get(f"https://openrouter.ai{path}", headers={"Authorization": f"Bearer {value}"}, timeout=15)
                if r.status_code != 404:
                    break
            if r.status_code != 200:
                return False, f"OpenRouter refused this key ({r.status_code}): {r.text[:120]}"
            d = r.json().get("data", {})
            limit = d.get("limit")
            return True, f"Valid · ${float(d.get('usage') or 0):.2f} used" + (f" of ${float(limit):.2f} limit" if limit else " · no spending limit set")
        r = httpx.get("https://api.hubapi.com/crm/v3/objects/companies", params={"limit": 1},
                      headers={"Authorization": f"Bearer {value}"}, timeout=15)
        if r.status_code != 200:
            return False, f"HubSpot refused this key ({r.status_code}): {r.text[:120]}"
        return True, "Valid"
    except httpx.HTTPError as e:
        return False, f"Couldn't reach the service to check the key: {e}"


_checks = {}


def health(name):
    """Whether the key in use actually works, cached for five minutes."""
    value = get(name)
    if not value:
        return {"ok": False, "detail": "Not set"}
    hit = _checks.get(name)
    if hit and hit[0] == value and time.time() - hit[1] < 300:
        return hit[2]
    ok, detail = check(name, value)
    result = {"ok": ok, "detail": detail}
    _checks[name] = (value, time.time(), result)
    return result


def put(name, value):
    """Save (or with an empty value, remove) a key, after checking it works. Returns an error message, or None."""
    value = (value or "").strip()
    if value and not value.startswith(PREFIX[name]):
        return f"That doesn't look like a {'HubSpot service key' if name == 'hubspot' else 'OpenRouter key'} (it should start with {PREFIX[name]})"
    if value:
        ok, detail = check(name, value)
        if not ok:
            return detail + " · The key was not saved."
    with closing(pipeline.connect(pipeline.DB)) as con:
        if value:
            con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (f"secret:{name}", value))
        else:
            con.execute("DELETE FROM settings WHERE key = ?", (f"secret:{name}",))
        con.commit()
    _cache.pop(name, None)
    _checks.pop(name, None)
    return None
