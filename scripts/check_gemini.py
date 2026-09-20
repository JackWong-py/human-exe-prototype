#!/usr/bin/env python3
"""Check that your Gemini key and model really work, before anything depends on them (Task 3).

    python scripts/check_gemini.py --models    # list the model names your key can use
    python scripts/check_gemini.py             # 1) text test  2) vision test on a scanned page

Settings come from .env (never committed):
    GEMINI_API_KEY=...        the key
    GEMINI_MODEL=...          one of the names printed by --models

The key is never printed.
"""
import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                      # pragma: no cover
    pass

TEST_SCAN = "attachments/email_512_SI.pdf"


def list_models(client, limit=40):
    """Names of the Gemini models this key can see."""
    names = [m.name for m in client.models.list()]
    return [n.replace("models/", "") for n in names if "gemini" in n.lower()][:limit]


def run_checks(client, model, page_image=None):
    """Returns [(name, ok, detail)]. Never raises: every problem is reported as a failed check."""
    results = []

    def check(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:         # noqa: BLE001 - the whole point is to report any failure
            ok, detail = False, f"{type(exc).__name__}: {str(exc)[:160]}"
        results.append((name, ok, detail))

    def text_test():
        reply = (client.models.generate_content(model=model, contents="Reply with the single word: ready").text or "").strip()
        return ("ready" in reply.lower(), f"the model answered: {reply[:60]!r}")

    check("text request", text_test)

    if page_image is not None:
        def vision_test():
            from app.readers import scan
            pairs, title = scan._vision_pairs([page_image], client)
            shown = "; ".join(f"{p[0]}={p[1][:24]}" for p in pairs[:7])
            return (len(pairs) >= 5, f"{len(pairs)} of 7 fields read, title {title!r}: {shown}")
        check("vision request (reads a scanned page)", vision_test)
    return results


def _scan_image():
    import pdfplumber
    from app.inbox import get_inbox
    from app.readers import scan
    data = get_inbox().read_bytes(TEST_SCAN)
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return scan._render(pdf.pages[0])[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", action="store_true", help="only list the model names")
    args = ap.parse_args()

    key, model = os.environ.get("GEMINI_API_KEY", ""), os.environ.get("GEMINI_MODEL", "")
    print(f"GEMINI_API_KEY: {'set (%d characters)' % len(key) if key else 'NOT SET'}")
    print(f"GEMINI_MODEL:   {model or 'NOT SET'}")
    if not key:
        sys.exit("Put GEMINI_API_KEY=... in the .env file (one line, no quotes) and run again.")
    try:
        from google import genai
    except ImportError:
        sys.exit("The google-genai package is missing. Run: pip install -r requirements.txt")
    client = genai.Client()

    if args.models:
        try:
            for name in list_models(client):
                print("  ", name)
        except Exception as exc:         # noqa: BLE001
            sys.exit(f"Could not list models: {type(exc).__name__}: {str(exc)[:160]}")
        return
    if not model:
        sys.exit("Set GEMINI_MODEL in .env. Run with --models to see the names your key can use.")

    results = run_checks(client, model, _scan_image())
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
