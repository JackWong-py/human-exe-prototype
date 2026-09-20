"""
scripts/score.py  (Member A)

Run the classifier over every email, build submission.json, optionally submit
it to the organizers' server, and record the run so we can compare experiments.

    # dry run against a folder (no scoring)
    python3 scripts/score.py --note "dry run"

    # real run against the server
    export INBOX_SOURCE=http://localhost:8080
    python3 scripts/score.py --note "baseline" --submit

Each run writes scores/<timestamp>/submission.json and appends a row to
scores/log.csv (note, source, total, failed, category counts, score). Keep
scores/log.csv in git; add scores/*/ to .gitignore.

Until B/C/D replace their stubs, statuses fall back to sample defaults, so only
the Stage-1 (classification) macro-F1 is meaningful between runs.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Allow running as `python3 scripts/score.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.classify import classify          # noqa: E402
from app.inbox import get_inbox            # noqa: E402
from app.submission import build_submission  # noqa: E402

SCORES_DIR = ROOT / "scores"
LOG_CSV = SCORES_DIR / "log.csv"


class _Result:
    """Minimal EmailResult stand-in for the classifier-only path.

    When E's pipeline is wired, score.py can be pointed at run_email instead;
    for now we classify and let build_submission apply sample defaults.
    """

    def __init__(self, category: str):
        self.category = category
        self.compare = None


def run_all(inbox):
    """Return ({email_id: _Result}, failed_ids). Never raises per-email."""
    results = {}
    failed = []
    for email in inbox.emails():
        eid = email.get("email_id", "?")
        try:
            results[eid] = _Result(classify(email).category)
        except Exception as exc:  # keep going; record the failure
            failed.append((eid, repr(exc)))
            results[eid] = _Result("GENERAL")
    return results, failed


def _append_log(row: dict):
    SCORES_DIR.mkdir(exist_ok=True)
    new_file = not LOG_CSV.exists()
    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build/score the SDOC submission.")
    parser.add_argument("--note", required=True, help="what changed this run")
    parser.add_argument("--submit", action="store_true",
                        help="POST to the server (needs an http INBOX_SOURCE)")
    parser.add_argument("--source", default=None,
                        help="override INBOX_SOURCE for this run")
    args = parser.parse_args(argv)

    inbox = get_inbox(args.source)
    results, failed = run_all(inbox)
    submission = build_submission(results)

    counts = Counter(v["category"] for v in submission.values())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = SCORES_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "submission.json").write_text(
        json.dumps(submission, indent=2), encoding="utf-8")

    print(f"{len(submission)} emails, {len(failed)} failed")
    print(f"categories: {dict(counts)}")
    if failed:
        for eid, err in failed[:10]:
            print(f"  FAILED {eid}: {err}", file=sys.stderr)

    score_summary = ""
    if args.submit:
        try:
            board = inbox.submit(submission)
            score_summary = json.dumps(board)
            print("scoreboard:", score_summary)
        except Exception as exc:
            print(f"submit failed: {exc!r}", file=sys.stderr)
            score_summary = f"submit_error:{exc!r}"

    _append_log({
        "time": stamp,
        "note": args.note,
        "source": str(inbox.source),
        "submitted": args.submit,
        "total": len(submission),
        "failed": len(failed),
        "BL_COMPARISON": counts.get("BL_COMPARISON", 0),
        "SI_REQUEST": counts.get("SI_REQUEST", 0),
        "INVOICE_QUERY": counts.get("INVOICE_QUERY", 0),
        "SPAM": counts.get("SPAM", 0),
        "GENERAL": counts.get("GENERAL", 0),
        "scoreboard": score_summary,
    })
    print(f"logged to {LOG_CSV}")


if __name__ == "__main__":
    main()
