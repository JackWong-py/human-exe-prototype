#!/usr/bin/env python3
"""Compare the vision model with OCR on the six scanned pages (Task 3).

    python scripts/vision_vs_ocr.py > docs/vision_vs_ocr.md

Needs GEMINI_API_KEY and GEMINI_MODEL in .env, and Tesseract installed. It makes 6 model requests.
For each scanned file it reads the 7 fields twice (OCR, then the model) and prints a table.
Three of the pages were also read by eye, so both readers are scored against what is printed.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                      # pragma: no cover
    pass

from app.contracts import CANONICAL_LABELS, FIELDS  # noqa: E402
from app.decide import compare_field  # noqa: E402
from app.inbox import get_inbox  # noqa: E402
from app.mapping import extract_fields  # noqa: E402
from app.normalize import first_line  # noqa: E402
from app.readers import scan  # noqa: E402

FILES = [(e, k) for e in ("email_512", "email_513", "email_514") for k in ("SI", "BL")]

# Read from the rendered pages by eye (see tests/test_pdf_scan.py).
TRUTH = {
    ("email_512", "SI"): ["APRIL FAR EAST (M) SDN BHD", "AL GURG STATIONERY LLC", "AL GURG STATIONERY LLC",
                          "NHAVA SHEVA, INDIA", "TUTICORIN, INDIA", "6 x 40'HC", "128,544 KG"],
    ("email_513", "SI"): ["APRIL FINE PAPER TRADING", "KPP-ANTALIS (SINGAPORE) PTE. LTD.", "EAST BRIGHT FZ-LLC",
                          "NHAVA SHEVA, INDIA", "VALPARAISO, CHILE", "10 x 40'HC", "237,750 KG"],
    ("email_514", "BL"): ["ASIA PACIFIC PAPERBOARD TRADING PTE LTD", "EAST BRIGHT FZ-LLC", "EAST BRIGHT FZ-LLC",
                          "NANTONG, CHINA", "GDANSK, POLAND", "1 x 20'FCL", "22,825 KG"],
}


def read_values(path, data, mode, client):
    """{field: value} read from one scan. mode is 'off' (OCR only) or 'always' (model first)."""
    previous = os.environ.get("SCAN_VISION")
    os.environ["SCAN_VISION"] = mode
    try:
        doc = scan.read_scan(path, data, client=client if mode == "always" else None)
    finally:                                   # put the setting back, or it leaks into every test that runs later
        if previous is None:
            os.environ.pop("SCAN_VISION", None)
        else:
            os.environ["SCAN_VISION"] = previous
    pairs = [p for p in doc.pairs if mode == "off" or p[2] == "vision model"]
    got = extract_fields(type(doc)(path=path, doc_type=doc.doc_type, pairs=pairs))
    return {f: first_line(got[f]["value"]) if f in got else "" for f in FIELDS}


def run(client, files=FILES, out=print):
    inbox = get_inbox()
    agree = total = 0
    right = {"OCR": 0, "vision": 0}
    truth_total = 0
    out("| file | field | OCR | vision | agree? |")
    out("|---|---|---|---|---|")
    for eid, kind in files:
        path = f"attachments/{eid}_{kind}.pdf"
        data = inbox.read_bytes(path)
        ocr = read_values(path, data, "off", client)
        vis = read_values(path, data, "always", client)
        truth = TRUTH.get((eid, kind))
        for i, f in enumerate(FIELDS):
            verdict = compare_field(f, ocr[f], vis[f], noisy=True) if ocr[f] and vis[f] else "missing"
            total += 1
            agree += verdict == "same"
            out(f"| {eid}_{kind} | {CANONICAL_LABELS[f]} | {ocr[f]} | {vis[f]} | {verdict} |")
            if truth:
                truth_total += 1
                for name, val in (("OCR", ocr[f]), ("vision", vis[f])):
                    right[name] += bool(val) and compare_field(f, truth[i], val, noisy=True) == "same"
    out("")
    out(f"OCR and the model agree on {agree} of {total} fields.")
    if truth_total:
        out(f"Against what is printed on the pages ({truth_total} fields read by eye): "
            f"OCR {right['OCR']}/{truth_total}, vision {right['vision']}/{truth_total}.")
    return {"agree": agree, "total": total, "right": right, "truth_total": truth_total}


def main():
    if not (os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_MODEL")):
        sys.exit("Set GEMINI_API_KEY and GEMINI_MODEL in .env first (see scripts/check_gemini.py).")
    client = scan._vision_client()
    if client is None:
        sys.exit("The google-genai package is missing. Run: pip install -r requirements.txt")
    run(client)


if __name__ == "__main__":
    main()
