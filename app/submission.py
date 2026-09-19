"""
app/submission.py  (Member A)

Builds submission.json in exactly the shape of sample_submission.json:

    "email_001": {"category": "...", "status": "...", "review_reason": null,
                  "defect_fields": [], "has_defect": false}

For BL_COMPARISON emails we copy the pipeline's comparison status/reason/defects.
For every other category we use the sample defaults. Shape must not change; if
the meaning changes, tell E.
"""
from __future__ import annotations

# Sample defaults for non-BL_COMPARISON emails (and for BL emails with no result yet).
_DEFAULTS = {
    "status": "OK",
    "review_reason": None,
    "defect_fields": [],
    "has_defect": False,
}


def _entry(category: str, compare=None) -> dict:
    """One submission entry. `compare` is an EmailResult.CompareResult or None."""
    entry = {"category": category, **_DEFAULTS}
    if category == "BL_COMPARISON" and compare is not None:
        entry["status"] = getattr(compare, "status", None) or "OK"
        entry["review_reason"] = getattr(compare, "review_reason", None)
        entry["defect_fields"] = list(getattr(compare, "defect_fields", []) or [])
        entry["has_defect"] = bool(getattr(compare, "has_defect", False))
    return entry


def build_submission(results: dict) -> dict:
    """
    results: {email_id: EmailResult} from the pipeline (E). Each EmailResult is
    expected to expose `.category` and an optional `.compare` (CompareResult).

    Falls back to sample defaults for any email whose comparison isn't wired yet,
    so the file always has one well-shaped entry per email.
    """
    submission = {}
    for email_id, res in results.items():
        category = getattr(res, "category", None) or "GENERAL"
        compare = getattr(res, "compare", None)
        submission[email_id] = _entry(category, compare)
    return submission
