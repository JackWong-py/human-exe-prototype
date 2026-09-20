from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


FIELDS = (
    "shipper",
    "consignee",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
    "description",
)


class CompareState(str, Enum):
    EQUAL = "equal"
    DIFFERENT = "different"
    UNKNOWN = "unknown"


class DecisionStatus(str, Enum):
    OK = "OK"
    MISMATCH = "MISMATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(slots=True)
class RawDoc:
    """
    Hand-written fixture / parser output.

    `fields` is deliberately loose: labels are raw labels exactly as extracted
    from the document and values are the corresponding raw values.
    """
    doc_type: str | None
    fields: Mapping[str, Any] = field(default_factory=dict)
    attachment_present: bool = True
    error: str | None = None
    noisy: bool = False
    source_name: str | None = None


@dataclass(slots=True)
class MappedDoc:
    doc_type: str | None
    values: dict[str, Any]
    attachment_present: bool = True
    error: str | None = None
    noisy: bool = False
    source_name: str | None = None


@dataclass(slots=True)
class FieldDiff:
    field: str
    left_raw: Any
    right_raw: Any
    left_normalized: Any
    right_normalized: Any
    state: CompareState
    ratio: float | None = None


@dataclass(slots=True)
class Decision:
    status: DecisionStatus
    reasons: list[str] = field(default_factory=list)
    diffs: list[FieldDiff] = field(default_factory=list)
