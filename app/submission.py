"""A owns this. Minimal builder so E can expose /submission today.

Shape must match sample_submission.json exactly. Non-BL emails get the sample's
default values.
"""


def build_submission(results):
    sub = {}
    for r in results:
        cat = r.get("category") or "GENERAL"
        if cat != "BL_COMPARISON" or not r.get("status"):
            sub[r["email_id"]] = {"category": cat, "status": "OK", "review_reason": None,
                                  "defect_fields": [], "has_defect": False}
        else:
            sub[r["email_id"]] = {"category": cat, "status": r["status"],
                                  "review_reason": r.get("review_reason"),
                                  "defect_fields": list(r.get("defect_fields") or []),
                                  "has_defect": bool(r.get("has_defect"))}
    return dict(sorted(sub.items()))
