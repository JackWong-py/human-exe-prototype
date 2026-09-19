"""Orchestrator: classify -> read documents -> decide, with visible failures and human review."""
import traceback
from dataclasses import asdict

from . import classify as clf
from . import db, decide as dec, readers
from .contracts import CANONICAL_LABELS, FIELDS, RawDoc
from .inbox import get_inbox


class NotFound(Exception):
    pass


class StageError(Exception):
    """Wraps any failure with the stage it happened in, so nothing fails silently."""

    def __init__(self, stage, cause):
        super().__init__(f"{stage}: {cause}")
        self.stage, self.cause = stage, cause


def _stage(name, fn, *args):
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001 - every failure must be recorded, whatever it is
        raise StageError(name, exc) from exc


def _base(email):
    return {"email_id": email["email_id"], "subject": email.get("subject", ""),
            "sender": email.get("from", "")}


def process(email):
    """Pure pipeline for one email. Returns a result dict; writes nothing."""
    c = _stage("classify", clf.classify, email)
    out = {**_base(email), "category": c.category, "confidence": c.confidence, "rule": c.rule,
           "status": None, "review_reason": None, "has_defect": False, "defect_fields": [],
           "diffs": [], "message": "", "evidence": {}}
    if c.category != "BL_COMPARISON":
        out["message"] = "Classified only; no document check for this category"
        return out
    si, bl = _stage("read_documents", readers.find_si_bl, email, get_inbox())
    res = _stage("decide", dec.decide, si, bl)
    out.update(status=res.status, review_reason=res.review_reason, has_defect=res.has_defect,
               defect_fields=list(res.defect_fields), diffs=list(res.diffs), message=res.message,
               evidence={"si": asdict(si) if si else None, "bl": asdict(bl) if bl else None})
    return out


def run_email(email_id, email=None, force=False):
    """Process one email and store the outcome. A failure is stored, never swallowed."""
    existing = db.get_result(email_id)
    if existing and existing["resolved_by_human"] and not force:
        return existing  # a human decision is never silently overwritten
    try:
        if email is None:
            email = _stage("load_email", get_inbox().get, email_id)
        out = process(email)
    except StageError as err:
        attempt = db.log_error(email_id, err.stage, str(err.cause), traceback.format_exc())
        base = _base(email) if email else {"email_id": email_id}
        db.save_result({**base, "category": (existing or {}).get("category"),
                        "state": "FAILED", "error_stage": err.stage,
                        "error_message": str(err.cause)})
        db.audit(email_id, "failed", {"stage": err.stage, "error": str(err.cause), "attempt": attempt})
        return db.get_result(email_id)
    out["state"] = "DONE"
    db.save_result(out)
    if out["status"] == "NEEDS_REVIEW":
        db.open_review(email_id, out["review_reason"], out["evidence"])
    else:
        db.supersede_open_reviews(email_id)
    return db.get_result(email_id)


def run_all(force=False):
    for email in get_inbox().emails():
        run_email(email["email_id"], email=email, force=force)
    return db.summary()


def retry(email_id):
    row = db.get_result(email_id)
    if row is None:
        raise NotFound(f"No result for {email_id}; run it first")
    db.audit(email_id, "retry", {"previous_state": row["state"]})
    return run_email(email_id)


# ---- human in the loop -----------------------------------------------------
def _doc_with_overrides(doc_dict, kind, values):
    """Build a RawDoc that carries the reviewer's typed values ahead of the reader's pairs."""
    human = [[CANONICAL_LABELS[f], str(v).strip(), "reviewer"]
             for f, v in (values or {}).items() if f in FIELDS and str(v).strip()]
    if not human:
        return RawDoc(**doc_dict) if doc_dict else None
    doc = RawDoc(**doc_dict) if doc_dict else RawDoc(path="(entered by reviewer)", title="REVIEWER INPUT")
    doc.pairs = human + [list(p) for p in doc.pairs]  # first match wins
    doc.doc_type, doc.error = kind, None              # the reviewer vouches for this document
    return doc


def resolve_review(review_id, by="reviewer", note="", verdict=None, defect_fields=None,
                   si_values=None, bl_values=None):
    """Close a review either with a verdict, or with corrected values that re-run decide()."""
    rv = db.get_review(review_id)
    if rv is None:
        raise NotFound(f"Review {review_id} not found")
    if rv["state"] != "OPEN":
        raise ValueError(f"Review {review_id} is already {rv['state']}")
    email_id = rv["email_id"]
    before = db.get_result(email_id)
    evidence = rv["evidence"] or {}

    if verdict:
        verdict = verdict.upper()
        if verdict not in ("OK", "MISMATCH"):
            raise ValueError("verdict must be OK or MISMATCH")
        fields = list(defect_fields or [])
        if set(fields) - set(FIELDS):
            raise ValueError(f"unknown field(s): {sorted(set(fields) - set(FIELDS))}")
        if verdict == "MISMATCH" and not fields:
            raise ValueError("A MISMATCH verdict needs at least one defect field")
        new = {"status": verdict, "review_reason": None, "has_defect": verdict == "MISMATCH",
               "defect_fields": fields if verdict == "MISMATCH" else [],
               "diffs": before["diffs"] if verdict == "MISMATCH" else [],
               "message": "Confirmed by reviewer"}
    elif si_values or bl_values:
        si = _doc_with_overrides(evidence.get("si"), "SI", si_values)
        bl = _doc_with_overrides(evidence.get("bl"), "BL", bl_values)
        res = dec.decide(si, bl)
        if res.status == "NEEDS_REVIEW":
            raise ValueError(f"Still needs review ({res.review_reason}): {res.message}")
        new = {"status": res.status, "review_reason": None, "has_defect": res.has_defect,
               "defect_fields": list(res.defect_fields), "diffs": list(res.diffs),
               "message": f"{res.message} (after reviewer input)",
               "evidence": {"si": asdict(si) if si else None, "bl": asdict(bl) if bl else None}}
    else:
        raise ValueError("Provide a verdict or corrected values")

    db.update_result_human(email_id, new)
    db.close_review(review_id, {"by": by, "note": note, "verdict": verdict,
                                "si_values": si_values, "bl_values": bl_values})
    db.audit(email_id, "review_resolved", {
        "review_id": review_id, "by": by, "note": note,
        "before": {k: before.get(k) for k in ("status", "review_reason", "defect_fields")},
        "after": {k: new.get(k) for k in ("status", "review_reason", "defect_fields")}})
    return db.get_result(email_id)
