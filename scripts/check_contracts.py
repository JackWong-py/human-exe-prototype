#!/usr/bin/env python3
"""Check that every member's part fits the shared contract. Run from the repo root:

    python scripts/check_contracts.py

Each line is PASS, FAIL (with a hint about who should fix what) or SKIP. Nothing is changed;
a temporary database is used. The last check runs the whole pipeline and compares the totals
with the numbers expected when all parts are real. Those numbers come from D's fixtures, not
from the organizers' answer key.
"""
import importlib
import inspect
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "check.db")
os.environ.setdefault("SCAN_VISION", "off")          # never call a model from a check

EXPECTED = {
    "by_category": {"BL_COMPARISON": 129, "SI_REQUEST": 132, "INVOICE_QUERY": 75, "GENERAL": 144, "SPAM": 40},
    "by_status": {"OK": 66, "MISMATCH": 46, "NEEDS_REVIEW": 17},
    "reasons": {"wrong_doc_type": 5, "missing_attachment": 5, "missing_value": 5, "unreadable": 2},
}
results = []


class Skip(Exception):
    pass


def check(who, name, fn):
    try:
        results.append(("PASS", who, name, fn() or ""))
    except Skip as exc:
        results.append(("SKIP", who, name, str(exc)))
    except AssertionError as exc:
        results.append(("FAIL", who, name, str(exc)))
    except Exception as exc:                          # noqa: BLE001 - report every kind of breakage
        results.append(("FAIL", who, name, f"{type(exc).__name__}: {exc}"))


def load(module):
    try:
        return importlib.import_module(module)
    except Exception as exc:                          # noqa: BLE001
        raise AssertionError(f"cannot import {module}: {type(exc).__name__}: {exc}")


def has(module, *names):
    mod = load(module)
    missing = [n for n in names if not hasattr(mod, n)]
    assert not missing, f"{module} has no {', '.join(missing)}"
    return mod


def args_of(fn):
    return list(inspect.signature(fn).parameters)


def email(eid):
    from app.inbox import get_inbox
    return get_inbox().get(eid)


def find_pair(eid):
    from app.inbox import get_inbox
    return has("app.readers", "find_si_bl").find_si_bl(email(eid), get_inbox())


def is_rawdoc(doc):
    from app.contracts import RawDoc
    assert isinstance(doc, RawDoc), f"expected a RawDoc, got {type(doc).__name__}"
    for pair in doc.pairs:
        assert len(pair) >= 2 and isinstance(pair[0], str) and isinstance(pair[1], str), \
            f"every pair must be [label, value, evidence] with text; got {pair!r}"


# ---- shared -----------------------------------------------------------------
def contracts():
    c = has("app.contracts", "FIELDS", "RawDoc", "CompareResult", "CANONICAL_LABELS", "CATEGORIES")
    assert len(c.FIELDS) == 7, "FIELDS must list the 7 fields (do not edit app/contracts.py alone)"


# ---- A ----------------------------------------------------------------------
def a_classify():
    from app.contracts import CATEGORIES
    fn = has("app.classify", "classify").classify
    assert len(args_of(fn)) >= 1, "classify(email) must take the email dict"
    r = fn(email("email_001"))
    assert all(hasattr(r, a) for a in ("category", "confidence", "rule")), "classify must return .category .confidence .rule"
    assert r.category in CATEGORIES, f"unknown category {r.category!r}"
    return f"email_001 -> {r.category}"


def a_submission():
    fn = has("app.submission", "build_submission").build_submission
    sub = fn([{"email_id": "email_001", "category": "BL_COMPARISON", "status": "OK"},
              {"email_id": "email_002", "category": "GENERAL"}])
    keys = {"category", "status", "review_reason", "defect_fields", "has_defect"}
    assert set(sub) == {"email_001", "email_002"} and all(set(v) == keys for v in sub.values()), \
        f"each entry needs exactly the keys {sorted(keys)} (see sample_submission.json)"


# ---- B ----------------------------------------------------------------------
def b_shape():
    mod = has("app.readers", "read_document", "find_si_bl")
    assert args_of(mod.find_si_bl)[:2] == ["email", "inbox"], "find_si_bl must be find_si_bl(email, inbox)"
    if getattr(mod, "IS_STUB", False):
        raise AssertionError("app/readers/__init__.py is still the stub (IS_STUB = True): B's readers are not wired in")


def b_clean_pair():
    si, bl = find_pair("email_001")
    for doc, kind in ((si, "SI"), (bl, "BL")):
        is_rawdoc(doc)
        assert doc.doc_type == kind, f"email_001 {kind}: doc_type is {doc.doc_type!r}"
        assert len(doc.pairs) >= 7, f"email_001 {kind}: only {len(doc.pairs)} pairs were extracted"
        assert not doc.noisy and not doc.error


def b_missing():
    assert find_pair("email_506") == (None, None), "email_506 has no attachments: expected (None, None)"
    si, bl = find_pair("email_507")
    assert si is not None and bl is None, "email_507 has only an SI: expected (RawDoc, None)"


def b_wrong_doc():
    si, bl = find_pair("email_501")
    assert bl is not None and bl.doc_type == "OTHER", \
        f"email_501: the file named _BL is a commercial invoice; doc_type must come from the title, got {getattr(bl, 'doc_type', None)!r}"


def b_office_formats():
    from app.inbox import get_inbox
    wanted = {"xlsx": None, "docx": None}
    for e in get_inbox().emails():
        for ext in wanted:
            if wanted[ext] is None and any(a.lower().endswith("." + ext) for a in e["attachments"]):
                wanted[ext] = e["email_id"]
    for ext, eid in wanted.items():
        si, bl = find_pair(eid)
        for doc in (si, bl):
            is_rawdoc(doc)
            assert len(doc.pairs) >= 7 and doc.doc_type in ("SI", "BL"), f"{eid} (.{ext}): {doc.doc_type}, {len(doc.pairs)} pairs"
    return f"xlsx: {wanted['xlsx']}, docx: {wanted['docx']}"


# ---- C ----------------------------------------------------------------------
def c_pdf():
    from app.inbox import get_inbox
    pdf = has("app.readers.pdf", "read_pdf")
    assert args_of(pdf.read_pdf)[:2] == ["path", "data"], "read_pdf must be read_pdf(path, data)"
    inbox = get_inbox()
    good = pdf.read_pdf("attachments/email_059_SI.pdf", inbox.read_bytes("attachments/email_059_SI.pdf"))
    is_rawdoc(good)
    assert good.doc_type == "SI" and len(good.pairs) >= 7, f"email_059_SI.pdf: {good.doc_type}, {len(good.pairs)} pairs"
    bad = pdf.read_pdf("attachments/email_511_BL.pdf", inbox.read_bytes("attachments/email_511_BL.pdf"))
    assert bad.error == "unreadable", "the corrupt PDF (email_511_BL.pdf) must give error='unreadable'"


def c_wired_in():
    from app.inbox import get_inbox
    mod = has("app.readers", "read_document")
    doc = mod.read_document("attachments/email_059_SI.pdf", get_inbox())
    assert doc.doc_type == "SI" and len(doc.pairs) >= 7, \
        "B's read_document does not send .pdf files to C's read_pdf (see the snippet in C's guide, Step 6)"


# ---- D ----------------------------------------------------------------------
def d_shape():
    dec = has("app.decide", "decide")
    has("app.mapping", "extract_fields", "map_label")
    has("app.normalize", "is_placeholder", "norm_name", "norm_port", "norm_count", "norm_weight")
    assert getattr(dec, "IS_STUB", False) is False, "app/decide.py is still the stub (IS_STUB = True)"
    r = dec.decide(None, None)
    assert (r.status, r.review_reason) == ("NEEDS_REVIEW", "missing_attachment"), "decide(None, None) must be NEEDS_REVIEW / missing_attachment"


def d_real_pairs():
    dec = has("app.decide", "decide")
    si, bl = find_pair("email_001")
    assert dec.decide(si, bl).status == "OK", "email_001 must be OK"
    r = dec.decide(*find_pair("email_013"))
    assert (r.status, r.defect_fields) == ("MISMATCH", ["port_of_discharge"]), f"email_013: {r.status} {r.defect_fields}"
    r = dec.decide(*find_pair("email_516"))
    assert (r.status, r.review_reason) == ("NEEDS_REVIEW", "missing_value"), f"email_516: {r.status} {r.review_reason}"


# ---- E: the whole pipeline --------------------------------------------------
def e_pipeline():
    from app import db, pipeline
    s = pipeline.run_all()
    assert s["by_state"].get("FAILED", 0) == 0, f"{s['by_state']['FAILED']} emails FAILED: see /api/errors"
    reasons = {}
    for rv in db.list_reviews("OPEN"):
        reasons[rv["reason"]] = reasons.get(rv["reason"], 0) + 1
    actual = {"by_category": s["by_category"], "by_status": s["by_status"], "reasons": reasons}
    problems = [f"{k}: expected {EXPECTED[k]}, got {actual[k]}" for k in EXPECTED if actual[k] != EXPECTED[k]]
    assert not problems, "totals differ from the expected numbers: " + " | ".join(problems)
    return "totals match the expected numbers"


def e_api():
    load("app.api")


CHECKS = [
    ("all", "shared contract", contracts),
    ("A", "classify(email) returns category, confidence, rule", a_classify),
    ("A", "build_submission gives the sample's shape", a_submission),
    ("B", "readers module is real and has the right signatures", b_shape),
    ("B", "clean txt pair -> SI and BL with 7+ pairs", b_clean_pair),
    ("B", "missing attachments -> None", b_missing),
    ("B", "wrong document type comes from the title", b_wrong_doc),
    ("B", "xlsx and docx are read", b_office_formats),
    ("C", "read_pdf(path, data): text PDF and corrupt PDF", c_pdf),
    ("B+C", "read_document sends PDFs to read_pdf", c_wired_in),
    ("D", "decide, mapping and normalize exist and are not stubs", d_shape),
    ("B+C+D", "real pairs give the expected verdicts", d_real_pairs),
    ("E", "API imports", e_api),
    ("ALL", "whole pipeline: totals match the expected numbers", e_pipeline),
]

if __name__ == "__main__":
    for who, name, fn in CHECKS:
        check(who, name, fn)
    width = max(len(r[2]) for r in results)
    for status, who, name, note in results:
        print(f"{status:4s} [{who:5s}] {name:{width}s}  {note}")
    counts = {s: sum(1 for r in results if r[0] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\n{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    sys.exit(1 if counts["FAIL"] else 0)