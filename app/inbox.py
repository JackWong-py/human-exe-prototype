"""
app/inbox.py: one place that decides where emails come from.

The source is read from the INBOX_SOURCE environment variable, so "local folder" versus
"organizers' server" is a single switch for the API, the tests and scripts/score.py:

    export INBOX_SOURCE=/path/to/sdoc-hackathon-bundle   # a local folder
    export INBOX_SOURCE=http://localhost:8080            # the organizers' server

Without it, the repo's own data/ folder is used (an absolute path, so it works from any directory).
"""
from __future__ import annotations

import os
from pathlib import Path

from loader import Inbox

_DEFAULT = str(Path(__file__).resolve().parents[1] / "data")
_cache: dict[str, Inbox] = {}


def get_inbox(source: str | None = None) -> Inbox:
    """Return the Inbox for `source`, else INBOX_SOURCE, else the bundled data folder."""
    src = source or os.environ.get("INBOX_SOURCE") or _DEFAULT
    if src not in _cache:
        _cache[src] = Inbox(src)
    return _cache[src]


def reset_inbox() -> None:
    """Forget cached inboxes (only needed if you want a completely fresh Inbox object)."""
    _cache.clear()