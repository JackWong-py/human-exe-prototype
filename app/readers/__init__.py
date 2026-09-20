"""Entry point of the document readers: the pipeline calls only these two functions.

    read_document(path, inbox) -> RawDoc
    find_si_bl(email, inbox)   -> (RawDoc | None, RawDoc | None)

Who does what:
    B  text.py, xlsx.py, docx.py   read one .txt / .xlsx / .docx file from disk
    C  pdf.py, scan.py             read a .pdf (text layer, scan, or corrupt)
    E  this file                   wires them together and turns B's result into the shared RawDoc
                                   (app/contracts.py), so the rest of the system sees one shape.
"""
import os
import tempfile

from ..contracts import RawDoc
from .common import detect_doc_type, unreadable
from .pdf import read_pdf


def _from_b(path, b_doc):
    """B's readers return their own small RawDoc. Convert it to the shared one."""
    if b_doc.error:
        return unreadable(path, f"The file could not be read ({b_doc.error})")
    pairs = [[str(p[0]), "" if p[1] is None else str(p[1]), str(p[2]) if len(p) > 2 else ""] for p in b_doc.pairs]
    return RawDoc(path=path, doc_type=detect_doc_type(b_doc.title), title=b_doc.title, pairs=pairs,
                  error=None, noisy=b_doc.noisy)


def _read_office_or_text(path, data):
    """B's readers take a file on disk, so write the bytes to a temporary file first.

    (This also works when the emails come from the organizers' HTTP server, not just a folder.)
    """
    from . import docx as b_docx, text as b_text, xlsx as b_xlsx
    ext = os.path.splitext(path)[1].lower()
    reader = {".txt": b_text.read_txt, ".xlsx": b_xlsx.read_xlsx, ".docx": b_docx.read_docx}.get(ext)
    if reader is None:
        return unreadable(path, f"Unsupported file type {ext or '(none)'}")
    handle = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        handle.write(data)
        handle.close()
        return _from_b(path, reader(handle.name))
    finally:
        os.unlink(handle.name)


def read_document(path, inbox=None):
    data = inbox.read_bytes(path)
    if path.lower().endswith(".pdf"):
        return read_pdf(path, data)
    return _read_office_or_text(path, data)


def find_si_bl(email, inbox):
    """The file name (_SI / _BL) only says which slot a file was meant for.

    What the file really is comes from its title, so a commercial invoice named _BL is returned
    in the BL slot with doc_type "OTHER". D then reports it as a wrong document type.
    """
    si = bl = None
    for path in email.get("attachments") or []:
        name = path.upper()
        if "_SI." in name and si is None:
            si = read_document(path, inbox)
        elif "_BL." in name and bl is None:
            bl = read_document(path, inbox)
    return si, bl
