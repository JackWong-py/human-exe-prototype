# Show the scoreboard of a run in plain tables (Task 1)
# Latest run from scores/log.csv
# python scripts/show_scoreboard.py
# One summary line for every submitted run
# python scripts/show_scoreboard.py --all
# A scoreboard saved in a file
# python scripts/show_scoreboard.py FILE.json
# Output is Markdown, so you can paste it into docs/SCORES.md

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # find the project root folder
LOG = os.path.join(ROOT, "scores", "log.csv")                       # path to the log file


def prf(tp, fp, fn):
    # Work out precision, recall, and F1 score
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def render(board, title="Scoreboard"):
    # Turn the scoreboard data into a Markdown table
    s1, s3, rel, e2e = board["stage1"], board["stage3"], board["reliability"], board["end_to_end"]
    out = [f"### {title}", "",
           f"**final_score {board['final_score']:.4f}** = 0.30 x classification F1 ({s1['macro_f1']:.4f})"
           f" + 0.20 x defect F1 ({s3['defect_f1']:.4f}) + 0.50 x end-to-end ({e2e['rate']:.4f})", "",
           "| measure | value |", "|---|---|",
           f"| classification accuracy | {s1['accuracy']:.4f} |",
           f"| end-to-end (defects flagged with the exact fields) | {e2e['success']} of {e2e['total']} = {e2e['rate']:.4f} |",
           f"| defect precision / recall / F1 | {s3['defect_precision']:.3f} / {s3['defect_recall']:.3f} / {s3['defect_f1']:.3f} |",
           f"| field-level F1 | {s3['field_f1']:.3f} |",
           f"| emails with exactly the right defect fields | {s3['exact_match_rate']:.3f} (of {s3['doc_total']} comparable emails) |",
           f"| escalation recall / precision (reliability, not in the final score) | "
           f"{rel['escalation_recall']:.3f} / {rel['escalation_precision']:.3f} |", "",
           "| category | precision | recall | F1 | tp | fp | fn |", "|---|---|---|---|---|---|---|"]
    for cat, c in s1["per"].items():
        # Loop through each category and show its numbers
        p, r, f = prf(c["tp"], c["fp"], c["fn"])
        out.append(f"| {cat} | {p:.3f} | {r:.3f} | {f:.3f} | {c['tp']} | {c['fp']} | {c['fn']} |")
    wrong = sorted(((n, a, p) for a, row in s1["confusion"].items() for p, n in row.items() if a != p and n),
                   reverse=True)
    out += ["", "Classification mistakes (real category -> what we said):", ""]
    out += [f"- {a} -> {p}: {n} emails" for n, a, p in wrong] or ["- none"]
    out += ["", "Review reasons caught: " + ", ".join(
        f"{r} {v['caught']}/{v['total']}" for r, v in rel["per_reason"].items())]
    return "\n".join(out)


def last_boards():
    # Read past scoreboard runs from log.csv
    if not os.path.exists(LOG):
        sys.exit("scores/log.csv does not exist yet. Run scripts/score.py --submit first.")
    boards = []
    for row in csv.DictReader(open(LOG, encoding="utf-8")):
        text = (row.get("scoreboard") or "").strip()
        if text.startswith("{"):
            boards.append((row.get("time", "?"), row.get("note", ""), json.loads(text)))
    return boards


def main(argv):
    # decide what to show based on command line arguments
    if argv and argv[0] == "--all":
        # Show one summary line for every run
        for time, note, b in last_boards():
            print(f"{time}  {b['final_score']:.4f}  classification {b['stage1']['macro_f1']:.4f}  "
                  f"defects {b['stage3']['defect_f1']:.4f}  end-to-end {b['end_to_end']['rate']:.4f}  | {note}")
        return
    if argv:
        # Show scoreboard from a saved JSON file
        print(render(json.load(open(argv[0], encoding="utf-8")), title=os.path.basename(argv[0])))
        return
    boards = last_boards()
    if not boards:
        sys.exit("No submitted run found in scores/log.csv (was --submit used?).")
    time, note, board = boards[-1]
    # Show the latest run
    print(render(board, title=f"{time}: {note}"))


if __name__ == "__main__":
    main(sys.argv[1:])  # Run the main function with command line arguments