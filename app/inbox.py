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
