"""Text-layer PDFs -> RawDoc. Owned by C.

    read_pdf(path, data) -> RawDoc

`path` is the attachment path as it appears in the email (kept in RawDoc.path); `data` is the
file's bytes (B's dispatcher gets them from inbox.read_bytes(path), which works for a folder
and for the HTTP server). This function decides what kind of PDF it is:

    corrupt / not a PDF        -> RawDoc(error="unreadable")
    has a text layer           -> parsed here
    no text but has an image   -> handed to scan.read_scan (OCR)

It never raises for a bad file. A crash inside the parser itself is deliberately NOT caught,
so the pipeline shows the email as FAILED (with a stack trace) instead of hiding a bug.
"""
import io
import re
from collections import Counter

import pdfplumber

from ..contracts import RawDoc
from .common import detect_doc_type, unreadable

MIN_TEXT_CHARS = 20          # fewer characters than this: treat the page as having no text layer
LINE_TOLERANCE = 2.5         # words whose tops differ by less than this (in points) share a line
ROW_RX = re.compile(r"^([A-Z]{4}\d{7})\s+(\d+'\w+)\s+(?:.*\s)?([\d,]+)\s*$")      # container table row
HEADER_RX = re.compile(r"^CONTAINER\s+NO\b", re.I)                                  # container table header
COLON_RX = re.compile(r"^([A-Za-z][A-Za-z0-9 .()/&,'-]{1,60}?)\s*:\s*(.*)$")        # "Label: value"


def read_pdf(path, data):
    if not data:
        return unreadable(path, "The file is empty")
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
        pages = list(pdf.pages)
    except Exception as exc:                                  # corrupt, truncated or not a PDF
        return unreadable(path, f"The PDF cannot be opened ({type(exc).__name__}: {str(exc)[:80]})")
    with pdf:
        if not pages:
            return unreadable(path, "The PDF has no pages")
        if sum(len(p.chars) for p in pages) >= MIN_TEXT_CHARS:
            return _read_text(path, pages)
        if any(p.images for p in pages):
            from .scan import read_scan                       # imported late: OCR libraries are only needed here
            return read_scan(path, data)
        return unreadable(path, "The PDF has no text and no image")


def _lines(page):
    """Group words into lines, top to bottom. Words inside a line keep the order they were written in.

    use_text_flow matters: some labels are longer than their column and overlap the value. Sorting
    by position would interleave the two texts ("ConsCigEnReIEeX"); the writing order keeps them apart.
    """
    lines = []
    for word in page.extract_words(use_text_flow=True, keep_blank_chars=False):
        for line in lines:
            if abs(line["top"] - word["top"]) <= LINE_TOLERANCE:
                line["words"].append(word)
                break
        else:
            lines.append({"top": word["top"], "words": [word]})
    return sorted(lines, key=lambda line: line["top"])


def _value_column(lines):
    """x position where values start: the most common start of lines that begin well right of the labels."""
    left = min(w["x0"] for line in lines for w in line["words"])
    starts = [round(min(w["x0"] for w in line["words"])) for line in lines]
    far = [x for x in starts if x > left + 40]
    return Counter(far).most_common(1)[0][0] if far else left + 113


def _read_text(path, pages):
    title, pairs, rows = "", [], []
    for page_no, page in enumerate(pages, 1):
        lines = _lines(page)
        if not lines:
            continue
        if not title:
            title = " ".join(w["text"] for w in lines[0]["words"])
            lines = lines[1:]
        value_x = _value_column(lines) if lines else 0
        in_fields, current = True, None
        for n, line in enumerate(lines, 1):
            text = " ".join(w["text"] for w in line["words"])
            evidence = f"page {page_no} line {n}"
            row = ROW_RX.match(text)
            if row or HEADER_RX.match(text):                  # the container table starts: labels stop here
                in_fields, current = False, None
                if row:
                    rows.append((row.group(2), int(row.group(3).replace(",", ""))))
                continue
            label_words = [w for w in line["words"] if w["x0"] < value_x - 3]
            value_words = sorted((w for w in line["words"] if w["x0"] >= value_x - 3), key=lambda w: w["x0"])
            colon = COLON_RX.match(text)
            if colon and (not in_fields or any(":" in w["text"] for w in label_words)):
                current = [colon.group(1).strip(), colon.group(2).strip(), evidence]      # "TOTAL Gross Wt (kgs): 131,322 KG"
                pairs.append(current)
            elif in_fields and label_words:
                current = [" ".join(w["text"] for w in label_words),
                           " ".join(w["text"] for w in value_words), evidence]           # label column + value column
                pairs.append(current)
            elif in_fields and current is not None:                                      # more lines of the same value
                current[1] = (current[1] + " | " if current[1] else "") + text
    _roll_up(pairs, rows)
    return RawDoc(path=path, doc_type=detect_doc_type(title), title=title, pairs=pairs)


def _roll_up(pairs, rows):
    """Many PDFs list the containers in a table and never print a total. Count and sum the rows."""
    if not rows:
        return
    total = sum(weight for _, weight in rows)
    kinds = Counter(kind for kind, _ in rows)
    printed_count = next((p for p in pairs if re.search(r"containers?\b", p[0], re.I)
                          and not re.search(r"container\s*no", p[0], re.I)), None)
    printed_weight = next((p for p in pairs if re.search(r"\bgross\b", p[0], re.I)), None)

    if printed_count is None:
        label = f"{len(rows)} x {kinds.most_common(1)[0][0]}"
        pairs.append(["Container Count", label + (" (mixed types)" if len(kinds) > 1 else ""),
                      f"container table roll-up ({len(rows)} rows)"])
    elif _first_int(printed_count[1]) != len(rows):
        printed_count[2] += f"; the container table has {len(rows)} rows"

    if printed_weight is None:
        pairs.append(["Gross Weight (KG)", f"{total:,}", f"container table roll-up ({len(rows)} rows)"])
    elif _first_int(printed_weight[1].replace(",", "")) != total:
        printed_weight[2] += f"; the container table sums to {total:,}"


def _first_int(text):
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None
