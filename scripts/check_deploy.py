#!/usr/bin/env python3
"""Check a running copy of the app, on your laptop or on Vercel. Uses only Python's standard library.

    python3 scripts/check_deploy.py https://your-project.vercel.app
    python3 scripts/check_deploy.py http://localhost:8000 --ai      # also try the real AI model

The first request to a sleeping Vercel container can take a while, so the script waits up to 90 seconds
for the app to answer. Every line is PASS or FAIL. Exit code 1 if anything failed.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def call(url, method="GET", timeout=60):
    request = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="the address of the app, for example https://your-project.vercel.app")
    ap.add_argument("--emails", type=int, default=520, help="how many emails the inbox has (default 520)")
    ap.add_argument("--ai", action="store_true", help="also ask the real AI model for a draft reply")
    args = ap.parse_args()
    base = args.url.rstrip("/")
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))

    # 1) wait for the app to wake up
    started, health = time.time(), None
    while time.time() - started < 90:
        try:
            status, body = call(base + "/api/health", timeout=30)
            if status == 200:
                health = json.loads(body)
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
            pass
        print("      waiting for the app to wake up...")
        time.sleep(5)
    check("the app answers /api/health", health is not None, f"after {time.time() - started:.0f} seconds")
    if health is None:
        sys.exit("The app never answered. On Vercel, open the project's Logs tab and read the newest error.")
    check("no stub modules are still active", health.get("stub_modules") == [], str(health.get("stub_modules")))
    print(f"      the emails come from: {health.get('inbox_source')}")

    # 2) the results exist
    status, body = call(base + "/api/summary")
    summary = json.loads(body) if status == 200 else {}
    check(f"the summary has all {args.emails} emails", summary.get("total") == args.emails, f"total = {summary.get('total')}")
    print(f"      categories: {summary.get('by_category')}")
    print(f"      outcomes of the document checks: {summary.get('by_status')}   open reviews: {summary.get('open_reviews')}")
    check("no email failed", not summary.get("by_state", {}).get("FAILED"), str(summary.get("by_state")))

    # 3) the pages
    for path, expected in (("/", None), ("/report", "Shipping document verification"), ("/reviews-ui", "Review queue")):
        status, body = call(base + path)
        check(f"page {path} opens", status == 200 and (expected is None or expected in body), f"HTTP {status}")

    # 4) drafted replies (task 4)
    status, body = call(base + "/api/results/email_507/draft?ai=false", method="POST")
    draft = json.loads(body) if status == 200 else {}
    check("a template draft reply can be made", status == 200 and draft.get("source") == "template" and "Dear" in draft.get("body", ""), f"HTTP {status}")
    if args.ai:
        status, body = call(base + "/api/results/email_507/draft?ai=true", method="POST", timeout=90)
        draft = json.loads(body) if status == 200 else {}
        print(f"      AI draft: source = {draft.get('source')}, note = {draft.get('note')}")
        check("the AI draft request was answered", status == 200 and bool(draft.get("body")), f"HTTP {status}")

    passed = sum(results)
    print(f"\n{passed} of {len(results)} checks passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
