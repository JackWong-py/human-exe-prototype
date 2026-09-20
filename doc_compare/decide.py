from __future__ import annotations

from compare import compare_docs
from models import CompareState, Decision, DecisionStatus, MappedDoc
from normalize import is_missing


_ALLOWED_TYPES = {"si", "bl"}


def _canonical_type(doc_type: str | None) -> str | None:
    if doc_type is None:
        return None
    text = str(doc_type).strip().casefold()
    aliases = {
        "shipping instruction": "si",
        "shipping instructions": "si",
        "si": "si",
        "bill of lading": "bl",
        "b/l": "bl",
        "bl": "bl",
    }
    return aliases.get(text, text)


def _missing_fields(doc: MappedDoc) -> list[str]:
    return [
        field
        for field, value in doc.values.items()
        if is_missing(value)
    ]


def decide(left: MappedDoc, right: MappedDoc) -> Decision:
    """
    Precedence:
      1) missing attachment -> NEEDS_REVIEW / missing_attachment
      2) wrong doc type -> NEEDS_REVIEW / wrong_doc_type
      3) document error -> NEEDS_REVIEW / unreadable
      4) missing value -> NEEDS_REVIEW / missing_value
      5) compare -> MISMATCH or OK
    """
    if not left.attachment_present or not right.attachment_present:
        return Decision(
            status=DecisionStatus.NEEDS_REVIEW,
            reasons=["missing_attachment"],
        )

    lt = _canonical_type(left.doc_type)
    rt = _canonical_type(right.doc_type)
    if lt not in _ALLOWED_TYPES or rt not in _ALLOWED_TYPES or {lt, rt} != _ALLOWED_TYPES:
        return Decision(
            status=DecisionStatus.NEEDS_REVIEW,
            reasons=["wrong_doc_type"],
        )

    if left.error or right.error:
        return Decision(
            status=DecisionStatus.NEEDS_REVIEW,
            reasons=["unreadable"],
        )

    missing = _missing_fields(left) + _missing_fields(right)
    if missing:
        return Decision(
            status=DecisionStatus.NEEDS_REVIEW,
            reasons=["missing_value"],
        )

    diffs = compare_docs(left, right)
    different = [d for d in diffs if d.state is CompareState.DIFFERENT]

    if different:
        return Decision(
            status=DecisionStatus.MISMATCH,
            reasons=[d.field for d in different],
            diffs=diffs,
        )

    return Decision(
        status=DecisionStatus.OK,
        reasons=[],
        diffs=diffs,
    )
