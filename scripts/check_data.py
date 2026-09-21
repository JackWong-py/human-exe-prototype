#!/usr/bin/env python3
"""Check that your copy of the data folder is exactly the organizers' data.

    python3 scripts/check_data.py            (on Windows: python scripts/check_data.py)

Why: on Windows, Git can silently change line endings inside files it thinks are text, and that
breaks some PDFs (for example email_499_BL.pdf becomes "unreadable"). Then the results on your
computer differ from everyone else's. This prints OK, or lists every file that differs.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CHECKSUMS = os.path.join(ROOT, "scripts", "data_checksums.json")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def check(data_dir=DATA, checksums=CHECKSUMS):
    """Returns (changed, missing, extra) lists of relative file names."""
    with open(checksums, encoding="utf-8") as fh:
        expected = json.load(fh)
    changed, missing, found = [], [], set()
    for name, digest in sorted(expected.items()):
        path = os.path.join(data_dir, *name.split("/"))
        if not os.path.exists(path):
            missing.append(name)
            continue
        found.add(name)
        if sha256(path) != digest:
            changed.append(name)
    extra = []
    for sub in ("attachments", "inbox"):
        folder = os.path.join(data_dir, sub)
        if os.path.isdir(folder):
            extra += [f"{sub}/{f}" for f in sorted(os.listdir(folder)) if f"{sub}/{f}" not in expected]
    return changed, missing, extra


def main():
    if not os.path.isdir(DATA):
        sys.exit(f"No data folder at {DATA}")
    changed, missing, extra = check()
    if not (changed or missing or extra):
        print("OK: every data file is identical to the organizers' original.")
        return
    if changed:
        print(f"{len(changed)} file(s) were CHANGED on your computer:")
        for name in changed[:15]:
            print("   ", name)
        if len(changed) > 15:
            print(f"    ... and {len(changed) - 15} more")
    for label, names in (("MISSING", missing), ("NOT part of the original data", extra)):
        if names:
            print(f"{len(names)} file(s) {label}: " + ", ".join(names[:8]) + (" ..." if len(names) > 8 else ""))
    print("\nMost likely cause: Git changed line endings. Repair (PowerShell or terminal, in the project folder):")
    print("    git config core.autocrlf false")
    print("    (Windows)  Remove-Item -Recurse -Force data\\attachments      (Linux/macOS)  rm -rf data/attachments")
    print("    git checkout -- data/attachments")
    print("Then run this script again. Details: HOW_TO_RUN_TESTS.md, 'Windows extras', part C.")
    sys.exit(1)


if __name__ == "__main__":
    main()
