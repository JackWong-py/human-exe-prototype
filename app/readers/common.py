"""Helpers shared by the document readers (B: txt/xlsx/docx, C: pdf/scan)."""
import difflib
import re

from ..contracts import RawDoc

# Title keywords, letters only, so "BILL OF LADING", "BILLOF LADING" and "Bill  of  Lading" all match.
_OTHER = ("COMMERCIALINVOICE", "PACKINGLIST", "CERTIFICATEOFORIGIN")


def _letters(text):
    return re.sub(r"[^A-Z]", "", (text or "").upper())


def _found(letters, key, fuzzy):
    if key in letters:
        return True
    if not fuzzy:
        return False
    n = len(key)   # OCR may garble a letter or two: accept a window that is 85% similar
    return any(difflib.SequenceMatcher(None, letters[i:i + n], key).ratio() >= 0.85
               for i in range(max(1, len(letters) - n + 1)))


def detect_doc_type(title, fuzzy=False):
    """Decide what a document is from its TITLE, never from its file name.

    Returns "SI", "BL", "OTHER" (invoice, packing list, certificate of origin) or "UNKNOWN".
    Use fuzzy=True for OCR text.
    """
    letters = _letters(title)
    if any(_found(letters, key, fuzzy) for key in _OTHER):
        return "OTHER"
    if _found(letters, "INSTRUCTION", fuzzy):     # "SHIPPING INSTRUCTION", "BILL OF LADING INSTRUCTION"
        return "SI"
    if _found(letters, "BILLOFLADING", fuzzy):    # "BILL OF LADING (DRAFT)"
        return "BL"
    return "UNKNOWN"


def unreadable(path, why):
    """A RawDoc for a file that cannot be read. The reason is kept so a reviewer can see it."""
    return RawDoc(path=path, doc_type="UNKNOWN", title="", pairs=[["Reader note", why, "reader"]],
                  error="unreadable", noisy=False)
