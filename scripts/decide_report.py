#!/usr/bin/env python3
"""Show what decide() says about every SI + BL pair.

    python scripts/decide_report.py                     # all fixtures, one line each + summary
    python scripts/decide_report.py --only mismatch     # ok | mismatch | review
    python scripts/decide_report.py --email email_013   # field-by-field detail for one email
    python scripts/decide_report.py --live              # use the REAL readers (B and C) instead of fixtures
    python scripts/decide_report.py --compare           # real readers vs fixtures: list every email that differs
"""
import argparse
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import classify, readers  # noqa: E402
from app.contracts import FIELDS, RawDoc  # noqa: E402
from app.decide import compare_field, decide  # noqa: E402
from app.inbox import get_inbox  # noqa: E402
from app.mapping import extract_fields  # noqa: E402


def fixture_pairs():
    with open(os.path.join(ROOT, "fixtures", "rawdocs.json")) as fh:
        raw = json.load(fh)
    doc = lambda d: RawDoc(**d) if d else None            # noqa: E731
    return {eid: (doc(p["si"]), doc(p["bl"])) for eid, p in raw.items()}


def live_pairs():
    inbox, out = get_inbox(), {}
    for email in inbox.emails():
        if classify.classify(email).category == "BL_COMPARISON":
            try:
                out[email["email_id"]] = readers.find_si_bl(email, inbox)
            except Exception as exc:                        # noqa: BLE001
                print(f"! {email['email_id']}: reader crashed: {exc}")
    return out


def line(eid, r):
    what = ",".join(r.defect_fields) if r.status == "MISMATCH" else (r.review_reason or "")
    return f"{eid}  {r.status:13s} {what:38s} {r.message[:70]}"


def detail(eid, si, bl):
    r = decide(si, bl)
    print(line(eid, r))
    for name, d in (("SI", si), ("BL", bl)):
        print(f"  {name}: {'(none)' if d is None else f'{d.path}  type={d.doc_type} noisy={d.noisy} error={d.error}'}")
    if si is None or bl is None or si.error or bl.error:
        return
    fs, fb = extract_fields(si), extract_fields(bl)
    noisy = si.noisy or bl.noisy
    print(f"  {'field':18s} {'verdict':10s} SI  ->  BL")
    for f in FIELDS:
        a, b = fs.get(f, {}).get("value", "<missing>"), fb.get(f, {}).get("value", "<missing>")
        verdict = compare_field(f, a, b, noisy) if "<missing>" not in (a, b) else "missing"
        print(f"  {f:18s} {verdict:10s} {a[:38]!r}  ->  {b[:38]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["ok", "mismatch", "review"])
    ap.add_argument("--email")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()

    if args.compare:
        fx, live = fixture_pairs(), live_pairs()
        different = 0
        for eid in sorted(fx):
            a, b = decide(*fx[eid]), decide(*live.get(eid, (None, None)))
            if (a.status, a.review_reason, a.defect_fields) != (b.status, b.review_reason, b.defect_fields):
                different += 1
                print(f"{eid}\n   fixtures: {line('', a).strip()}\n   readers : {line('', b).strip()}")
        print(f"\n{different} of {len(fx)} emails differ between the fixtures and the real readers")
        return

    pairs = live_pairs() if args.live else fixture_pairs()
    if args.email:
        if args.email not in pairs:
            sys.exit(f"{args.email} is not a BL_COMPARISON email")
        return detail(args.email, *pairs[args.email])

    wanted = {"ok": "OK", "mismatch": "MISMATCH", "review": "NEEDS_REVIEW"}.get(args.only)
    counts = collections.Counter()
    for eid in sorted(pairs):
        r = decide(*pairs[eid])
        counts[(r.status, r.review_reason)] += 1
        if wanted is None or r.status == wanted:
            print(line(eid, r))
    print("\n" + "\n".join(f"{n:4d}  {s}{' / ' + why if why else ''}" for (s, why), n in sorted(counts.items())))


if __name__ == "__main__":
    main()
