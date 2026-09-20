#!/usr/bin/env python3
"""Build the sheet used to check the system's answers by eye (Task 2).

    python scripts/verification_sheet.py

Writes verification/verification_sheet.csv (open it in Excel, LibreOffice or Google Sheets).
It lists:
  * every MISMATCH        -> is the difference REAL, or a false alarm caused by formatting?
  * 15 random OK pairs    -> did the system MISS a defect? (same 15 every time)
  * every NEEDS_REVIEW    -> is the reason right?

For each row you get the two source files and the 7 values the system read from each, so you
can open the files and compare. Fill in the last three columns: checked_by, verdict, notes.
Verdict words: CONFIRMED, FALSE_ALARM, MISSED_DEFECT, WRONG_REASON, UNSURE.
"""
import csv
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SCAN_VISION", "off")     # this sheet must never call a model

from app import pipeline  # noqa: E402
from app.contracts import CANONICAL_LABELS, FIELDS, RawDoc  # noqa: E402
from app.inbox import get_inbox  # noqa: E402
from app.mapping import extract_fields  # noqa: E402
from app.normalize import first_line  # noqa: E402

OK_SAMPLE_SIZE = 15
SEED = 42            # keeps the "random" OK sample the same for everyone


def values(doc_dict):
    """{field: first line of the value} for one document, or {} if there is none."""
    if not doc_dict:
        return {}
    got = extract_fields(RawDoc(**doc_dict))
    return {f: first_line(got[f]["value"]) if f in got else "(missing)" for f in FIELDS}


def main():
    inbox = get_inbox()
    rows, ok_ids = [], []
    for email in inbox.emails():
        result = pipeline.process(email)
        if result["category"] != "BL_COMPARISON":
            continue
        if result["status"] == "OK":
            ok_ids.append(result["email_id"])
        rows.append(result)

    ok_pick = set(random.Random(SEED).sample(sorted(ok_ids), min(OK_SAMPLE_SIZE, len(ok_ids))))
    groups = {"MISMATCH": 0, "NEEDS_REVIEW": 1, "OK_SAMPLE": 2}
    picked = []
    for r in rows:
        if r["status"] == "MISMATCH":
            picked.append(("MISMATCH", r))
        elif r["status"] == "NEEDS_REVIEW":
            picked.append(("NEEDS_REVIEW", r))
        elif r["email_id"] in ok_pick:
            picked.append(("OK_SAMPLE", r))
    picked.sort(key=lambda g: (groups[g[0]], g[1]["email_id"]))

    header = ["group", "email_id", "system_says", "fields_flagged_or_reason", "si_file", "bl_file"]
    for f in FIELDS:
        header += [f"{f} (SI)", f"{f} (BL)"]
    header += ["checked_by", "verdict", "notes"]

    os.makedirs(os.path.join(ROOT, "verification"), exist_ok=True)
    path = os.path.join(ROOT, "verification", "verification_sheet.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:     # utf-8-sig so Excel shows accents
        writer = csv.writer(fh)
        writer.writerow(header)
        for group, r in picked:
            ev = r.get("evidence") or {}
            si, bl = ev.get("si"), ev.get("bl")
            si_vals, bl_vals = values(si), values(bl)
            what = ", ".join(r["defect_fields"]) if r["status"] == "MISMATCH" else (r["review_reason"] or "")
            row = [group, r["email_id"], r["status"], what,
                   si["path"] if si else "(none)", bl["path"] if bl else "(none)"]
            for f in FIELDS:
                row += [si_vals.get(f, ""), bl_vals.get(f, "")]
            row += ["", "", ""]
            writer.writerow(row)

    counts = {g: sum(1 for x, _ in picked if x == g) for g in groups}
    print(f"wrote {path}")
    print(f"rows: {counts}  (total {len(picked)})")
    print("Source files are in the data/attachments folder. Fields: " + ", ".join(CANONICAL_LABELS[f] for f in FIELDS))


if __name__ == "__main__":
    main()
