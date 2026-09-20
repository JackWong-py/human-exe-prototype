from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from models import CompareState, FieldDiff, FIELDS, MappedDoc
from normalize import normalize_field


FUZZY_EQUAL_THRESHOLD = 0.85


def _ratio(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return SequenceMatcher(None, str(left), str(right)).ratio()


def compare_field(
    field: str,
    left_raw: Any,
    right_raw: Any,
    *,
    noisy: bool = False,
    fuzzy_threshold: float = FUZZY_EQUAL_THRESHOLD,
) -> FieldDiff:
    left = normalize_field(field, left_raw)
    right = normalize_field(field, right_raw)

    if left is None or right is None:
        state = CompareState.UNKNOWN
        ratio = None
    elif left == right:
        state = CompareState.EQUAL
        ratio = 1.0
    else:
        ratio = _ratio(left, right)
        if noisy and ratio is not None and ratio >= fuzzy_threshold:
            state = CompareState.EQUAL
        else:
            state = CompareState.DIFFERENT

    return FieldDiff(
        field=field,
        left_raw=left_raw,
        right_raw=right_raw,
        left_normalized=left,
        right_normalized=right,
        state=state,
        ratio=ratio,
    )


def compare_docs(left: MappedDoc, right: MappedDoc) -> list[FieldDiff]:
    noisy = bool(left.noisy or right.noisy)
    return [
        compare_field(
            field,
            left.values.get(field),
            right.values.get(field),
            noisy=noisy,
        )
        for field in FIELDS
    ]
