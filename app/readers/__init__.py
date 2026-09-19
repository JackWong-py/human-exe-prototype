"""STUB owned by B (txt/xlsx/docx + find_si_bl) and C (pdf/scan).

The per-format files in this folder (text.py, xlsx.py, docx.py, pdf.py, scan.py) are
where the real readers go. This file is the entry point the pipeline calls:

    read_document(path, inbox) -> RawDoc
    find_si_bl(email, inbox)   -> (RawDoc | None, RawDoc | None)

The stub returns RawDocs with no pairs so the pipeline runs end to end today.
Replace the bodies, keep the signatures, and delete IS_STUB when you are done.
"""
from ..contracts import RawDoc

IS_STUB = True


def read_document(path, inbox=None):
    up = path.upper()
    kind = "SI" if "_SI" in up else "BL" if "_BL" in up else "UNKNOWN"
    return RawDoc(path=path, doc_type=kind, title="(stub)")


def find_si_bl(email, inbox):
    si = bl = None
    for p in email.get("attachments") or []:
        d = read_document(p, inbox)
        if d.doc_type == "SI" and si is None:
            si = d
        elif d.doc_type == "BL" and bl is None:
            bl = d
    return si, bl
