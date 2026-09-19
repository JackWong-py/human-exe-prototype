"""STUB owned by D. Applies only the review precedence, never compares fields.

Replace decide(), keep the signature, and delete IS_STUB when you are done.
"""
from .contracts import CompareResult

IS_STUB = True


def decide(si, bl):
    if si is None or bl is None:
        return CompareResult("NEEDS_REVIEW", review_reason="missing_attachment",
                             message="SI or BL attachment is missing")
    if si.doc_type == "OTHER" or bl.doc_type == "OTHER":
        return CompareResult("NEEDS_REVIEW", review_reason="wrong_doc_type",
                             message="An attachment is not an SI or a draft BL")
    if si.error or bl.error:
        return CompareResult("NEEDS_REVIEW", review_reason="unreadable",
                             message="An attachment could not be read")
    return CompareResult("OK", message="STUB: nothing was actually compared")
