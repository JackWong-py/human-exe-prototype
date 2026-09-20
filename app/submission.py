"""
app/submission.py  (Member A)

Builds submission.json in exactly the shape of sample_submission.json:

    "email_001": {"category": "...", "status": "...", "review_reason": null,
                  "defect_fields": [], "has_defect": false}

For BL_COMPARISON emails we copy the pipeline's comparison status/reason/defects.
For every other category we use the sample defaults. The shape must not change; if
the meaning changes, tell E.

build_submission accepts every shape the team's code produces, so nobody has to convert:

  * a list of result dicts   [{"email_id", "category", "status", "review_reason",
                               "defect_fields", "has_defect"}, ...]      (E: db.list_results(),
                                                                          pipeline.process())
  * a dict of result dicts   {email_id: {...}}
  * a dict of result objects {email_id: obj}  with .category and an optional .compare
                             (a CompareResult), or the comparison fields directly on obj  (A)

Any email whose comparison is not available yet gets the sample defaults, so the file always
has one well-shaped entry per email.
"""
from __future__ import annotations

# Sample defaults for non-BL_COMPARISON emails (and for BL emails with no result yet).
_DEFAULTS = {
    "status": "OK",
    "review_reason": None,
    "defect_fields": [],
    "has_defect": False,
}


def _get(item, name, default=None):
    """Read a field from a dict or from an object."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _entry(item) -> dict:
    """One submission entry from one result (a dict or an object)."""
    category = _get(item, "category") or "GENERAL"
    comparison = _get(item, "compare") or item      # A's results nest it under .compare; E's rows are flat
    status = _get(comparison, "status")
    if category != "BL_COMPARISON" or not status:
        return {"category": category, "status": _DEFAULTS["status"], "review_reason": None,
                "defect_fields": [], "has_defect": False}
    return {"category": category, "status": status,
            "review_reason": _get(comparison, "review_reason"),
            "defect_fields": list(_get(comparison, "defect_fields") or []),
            "has_defect": bool(_get(comparison, "has_defect"))}


def build_submission(results) -> dict:
    """{email_id: entry}, sorted by email_id. `results` may be a list or a dict (see the top)."""
    pairs = results.items() if isinstance(results, dict) else ((_get(r, "email_id"), r) for r in results)
    return dict(sorted((email_id, _entry(item)) for email_id, item in pairs))