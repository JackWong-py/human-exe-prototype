<<<<<<< HEAD
"""
app/inbox.py — one place that decides where emails come from.

Source is read from the INBOX_SOURCE env var so folder-vs-server is a single
switch for both the classifier smoke test and scripts/score.py:

    export INBOX_SOURCE=/path/to/sdoc-hackathon-bundle   # local folder
    export INBOX_SOURCE=http://localhost:8080            # organizers' server

Defaults to the repo's bundled ./data folder when unset.
"""
from __future__ import annotations

import os
from pathlib import Path

from loader import Inbox

_DEFAULT = str(Path(__file__).resolve().parents[1] / "data")


def get_inbox(source: str | None = None) -> Inbox:
    """Return an Inbox for the given source, INBOX_SOURCE, or the bundled data."""
    return Inbox(source or os.environ.get("INBOX_SOURCE") or _DEFAULT)
=======
"""One place that decides where emails come from (folder or HTTP server)."""
import os
from loader import Inbox

_inbox = None


def get_inbox():
    global _inbox
    if _inbox is None:
        _inbox = Inbox(os.environ.get("INBOX_SOURCE", "data"))
    return _inbox


def reset_inbox():
    global _inbox
    _inbox = None
>>>>>>> db16662c206ae14ae84853881eb4ce94aeb344f3
