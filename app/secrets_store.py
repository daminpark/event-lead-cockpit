"""API keys for HubSpot and OpenRouter: pasted in the cockpit's Settings (owner only), else from the server environment.

Values are stored on the server and never sent back to the browser; the page only learns whether a key is set
and its last four characters.
"""

import os
import time
from contextlib import closing

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


def put(name, value):
    """Save (or with an empty value, remove) a key. Returns an error message, or None."""
    value = (value or "").strip()
    if value and not value.startswith(PREFIX[name]):
        return f"That doesn't look like a {'HubSpot private app token' if name == 'hubspot' else 'OpenRouter key'} (it should start with {PREFIX[name]})"
    with closing(pipeline.connect(pipeline.DB)) as con:
        if value:
            con.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (f"secret:{name}", value))
        else:
            con.execute("DELETE FROM settings WHERE key = ?", (f"secret:{name}",))
        con.commit()
    _cache.pop(name, None)
    return None
