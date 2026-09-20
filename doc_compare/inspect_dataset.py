from __future__ import annotations

import argparse
from pathlib import Path

from dataset import discover_attachments, group_by_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "attachments",
        help=r"Real filesystem path to data_v2\attachments",
    )
    args = parser.parse_args()

    attachments = discover_attachments(args.attachments)
    groups = group_by_case(attachments)

    print(f"Found {len(attachments)} attachment files in {len(groups)} case groups.")
    print()

    suspicious = {
        case_id: files
        for case_id, files in groups.items()
        if len(files) != 2
    }

    if suspicious:
        print("Cases that do not currently have exactly 2 discovered attachments:")
        for case_id, files in list(suspicious.items())[:30]:
            print(f"  {case_id}: {len(files)} file(s)")
            for f in files:
                print(f"      {f.path}")
    else:
        print("Every discovered case currently has exactly 2 attachments.")

    print()
    print(
        "Next step: convert each attachment into RawDoc, then call "
        "pipeline.evaluate_pair(si_raw, bl_raw)."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
