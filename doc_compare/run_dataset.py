from __future__ import annotations

import argparse
import json
from pathlib import Path

from attachment_reader import rawdoc_from_attachment
from dataset import discover_attachments, group_by_case
from models import DecisionStatus
from pipeline import evaluate_pair


def _pick_si_bl(files):
    rawdocs = [rawdoc_from_attachment(item.path) for item in files]

    si = next((doc for doc in rawdocs if str(doc.doc_type).upper() == "SI"), None)
    bl = next((doc for doc in rawdocs if str(doc.doc_type).upper() == "BL"), None)

    return si, bl, rawdocs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read attachments and compare SI vs BL."
    )
    parser.add_argument(
        "attachments",
        help=r"Path to data_v2\attachments",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process N cases. 0 means all.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Optional output JSON file.",
    )
    parser.add_argument(
        "--show-mismatches",
        type=int,
        default=30,
        help="Print the first N mismatches.",
    )
    args = parser.parse_args()

    attachments = discover_attachments(args.attachments)
    grouped = group_by_case(attachments)

    items = sorted(grouped.items())
    if args.limit > 0:
        items = items[: args.limit]

    results = []
    mismatch_printed = 0

    for case_id, files in items:
        si, bl, rawdocs = _pick_si_bl(files)

        if si is None or bl is None:
            results.append(
                {
                    "case_id": case_id,
                    "status": "NEEDS_REVIEW",
                    "reasons": ["wrong_doc_type"],
                    "files": [doc.source_name for doc in rawdocs],
                    "detected_types": [doc.doc_type for doc in rawdocs],
                    "errors": [doc.error for doc in rawdocs if doc.error],
                }
            )
            continue

        result = evaluate_pair(si, bl)

        row = {
            "case_id": case_id,
            "status": result.status.value,
            "reasons": result.reasons,
            "si": si.source_name,
            "bl": bl.source_name,
        }

        if result.diffs:
            row["diffs"] = [
                {
                    "field": d.field,
                    "state": d.state.value,
                    "si_raw": d.left_raw,
                    "bl_raw": d.right_raw,
                    "si_normalized": d.left_normalized,
                    "bl_normalized": d.right_normalized,
                    "ratio": d.ratio,
                }
                for d in result.diffs
                if d.state.value != "equal"
            ]

        results.append(row)

        if (
            result.status is DecisionStatus.MISMATCH
            and mismatch_printed < args.show_mismatches
        ):
            mismatch_printed += 1
            print(f"\n[{case_id}] MISMATCH: {', '.join(result.reasons)}")
            for diff in result.diffs:
                if diff.state.value == "different":
                    ratio = "-" if diff.ratio is None else f"{diff.ratio:.3f}"
                    print(
                        f"  {diff.field}: "
                        f"{diff.left_raw!r} <> {diff.right_raw!r} "
                        f"(ratio={ratio})"
                    )

    counts = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    print("\nSummary")
    print("-------")
    print(f"attachment files: {len(attachments)}")
    print(f"cases processed : {len(results)}")
    for key in ("OK", "MISMATCH", "NEEDS_REVIEW"):
        print(f"{key:13}: {counts.get(key, 0)}")

    if args.json_path:
        out = Path(args.json_path)
        out.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
