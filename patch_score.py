#!/usr/bin/env python3
"""Make scripts/score.py run the WHOLE pipeline, not just the classifier.

Why: the original scripts/score.py only classifies emails. Every BL_COMPARISON email is then
submitted as OK with no defects, so the end-to-end and defect scores would be about zero.

Run from the repo root (the folder that contains scripts/ and app/):

    python3 patch_score.py

It changes only scripts/score.py, keeps a backup as scripts/score.py.bak, and stops without
changing anything if the file is not the version it expects.
"""
import shutil
import sys

PATH = "scripts/score.py"
text = open(PATH, encoding="utf-8").read()

if "pipeline.process" in text:
    sys.exit("scripts/score.py already runs the full pipeline. Nothing to do.")

edits = [
    # 1) import the pipeline instead of the classifier
    ("from app.classify import classify          # noqa: E402\n",
     "from app import pipeline                   # noqa: E402  (classify + read + compare)\n"),
    # 2) --source must also reach the pipeline, which reads attachments through get_inbox()
    ("import json\nimport sys\n", "import json\nimport os\nimport sys\n"),
    ("    inbox = get_inbox(args.source)\n",
     "    if args.source:\n"
     "        os.environ[\"INBOX_SOURCE\"] = args.source      # the pipeline reads attachments from the same place\n"
     "    inbox = get_inbox(args.source)\n"),
    # 3) show the BL outcomes, so an all-OK run is obvious at a glance
    ("    print(f\"categories: {dict(counts)}\")\n",
     "    print(f\"categories: {dict(counts)}\")\n"
     "    print(\"BL_COMPARISON outcomes:\",\n"
     "          dict(Counter(v[\"status\"] for v in submission.values() if v[\"category\"] == \"BL_COMPARISON\")))\n"),
]
for old, new in edits:
    if old not in text:
        sys.exit("scripts/score.py is not the expected version (could not find:\n" + old + ")\n"
                 "Nothing was changed. Send this message to the person who helps you.")
    text = text.replace(old, new, 1)

# 4) replace the classifier-only runner with a full-pipeline runner
start = text.find("class _Result:")
end = text.find("def _append_log")
if start < 0 or end < 0 or end < start:
    sys.exit("could not find the classifier-only runner. Nothing was changed.")
runner = '''def run_all(inbox):
    """Run the FULL pipeline (classify, read documents, compare) for every email.

    Returns (list of result dicts, failed). Never raises per email: a failed email is submitted
    as GENERAL so the file always has one entry per email, and it is listed in `failed`.
    Human decisions made on the review page are NOT included: this is the system's own answer.
    """
    results = []
    failed = []
    for email in inbox.emails():
        eid = email.get("email_id", "?")
        try:
            results.append(pipeline.process(email))
        except Exception as exc:  # keep going; record the failure
            failed.append((eid, repr(exc)))
            results.append({"email_id": eid, "category": "GENERAL"})
    return results, failed


'''
text = text[:start] + runner + text[end:]

shutil.copyfile(PATH, PATH + ".bak")
open(PATH, "w", encoding="utf-8").write(text)
print("scripts/score.py now runs the whole pipeline. Backup: scripts/score.py.bak")
print("Test it:  python3 scripts/score.py --note \"pipeline wired\"")
print("Expect a line like:  BL_COMPARISON outcomes: {'OK': 66, 'MISMATCH': 46, 'NEEDS_REVIEW': 17}")
