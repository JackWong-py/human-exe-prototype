#!/usr/bin/env python3
"""See what the PDF readers produce, for every PDF attachment in the inbox.

    python scripts/pdf_report.py                        # one line per PDF
    python scripts/pdf_report.py --file email_512_SI.pdf   # every pair, with its evidence
    python scripts/pdf_report.py --save-images /tmp/ocr    # save what Tesseract is shown for each scan
"""
import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pdfplumber  # noqa: E402

from app.contracts import FIELDS  # noqa: E402
from app.inbox import get_inbox  # noqa: E402
from app.readers import pdf, scan  # noqa: E402

try:                                            # D's mapping, if it has been merged
    from app.mapping import extract_fields
except ImportError:
    extract_fields = None


def all_pdfs():
    return sorted({a for e in get_inbox().emails() for a in e["attachments"] if a.lower().endswith(".pdf")})


def kind(doc):
    return "corrupt" if doc.error else "scan" if doc.noisy else "text"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="a name like email_512_SI.pdf")
    ap.add_argument("--save-images", metavar="DIR")
    args = ap.parse_args()
    inbox = get_inbox()

    paths = [p for p in all_pdfs() if not args.file or p.endswith(args.file)]
    for path in paths:
        data = inbox.read_bytes(path)
        doc = pdf.read_pdf(path, data)
        if args.file:
            print(f"{path}  kind={kind(doc)}  type={doc.doc_type}  error={doc.error}  title={doc.title!r}")
            for label, val, evidence in doc.pairs:
                print(f"  {label:38s} {val[:60]!r:64s} {evidence[:70]}")
            continue
        found = "-"
        if extract_fields and not doc.error:
            got = extract_fields(doc)
            found = f"{sum(f in got for f in FIELDS)}/7 fields"
        print(f"{path:38s} {kind(doc):8s} {doc.doc_type:8s} {len(doc.pairs):2d} pairs  {found}")
        if args.save_images and doc.noisy:
            os.makedirs(args.save_images, exist_ok=True)
            with pdfplumber.open(io.BytesIO(data)) as handle:
                img, dpi = scan._render(handle.pages[0])
                prepared = scan._prepare(img, dpi)
            prepared.save(os.path.join(args.save_images, os.path.basename(path).replace(".pdf", ".png")))
    if not args.file:
        print(f"\n{len(paths)} PDFs")


if __name__ == "__main__":
    main()
