from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from models import FIELDS, MappedDoc, RawDoc
from normalize import normalize_name


_CJK_RE = re.compile(
    "["
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "]"
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def clean_label(label: str) -> str:
    """
    Strip Chinese characters, lowercase, collapse punctuation/spacing.
    """
    label = _CJK_RE.sub(" ", label or "")
    label = label.lower().strip()
    label = _NON_ALNUM_RE.sub(" ", label)
    return " ".join(label.split())


ALIASES: dict[str, tuple[str, ...]] = {
    "shipper": (
        "shipper",
        "exporter",
        "consignor",
        "shipper exporter",
    ),
    "consignee": (
        "consignee",
        "consigned to",
        "to the order of",
        "to order of",
        "notify consignee",
    ),
    "port_of_loading": (
        "port of loading",
        "port loading",
        "loading port",
        "pol",
    ),
    "port_of_discharge": (
        "port of discharge",
        "port discharge",
        "discharge port",
        "pod",
    ),
    "container_count": (
        "container count",
        "container quantity",
        "number of containers",
        "no of containers",
        "containers",
        "container s",
    ),
    "gross_weight_kg": (
        "gross weight",
        "gross weight kg",
        "gross wt",
        "g w",
        "weight gross",
    ),
    "description": (
        "description",
        "description of goods",
        "goods description",
        "cargo description",
        "commodity",
    ),
}

IGNORE_LABELS = {
    "net weight",
    "net wt",
    "n w",
}


def _match_field(cleaned_label: str) -> str | None:
    if not cleaned_label or cleaned_label in IGNORE_LABELS:
        return None

    # Longest / most specific aliases first.
    candidates: list[tuple[int, str]] = []
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if cleaned_label == alias:
                candidates.append((len(alias), field))
            elif alias in cleaned_label:
                candidates.append((len(alias), field))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def map_doc(raw: RawDoc) -> MappedDoc:
    values: dict[str, Any] = {field: None for field in FIELDS}

    for raw_label, value in raw.fields.items():
        field = _match_field(clean_label(str(raw_label)))
        if field is None:
            continue

        # Keep the first meaningful value rather than overwriting it with blanks.
        current = values[field]
        if current not in (None, ""):
            continue
        values[field] = value

    return MappedDoc(
        doc_type=raw.doc_type,
        values=values,
        attachment_present=raw.attachment_present,
        error=raw.error,
        noisy=raw.noisy,
        source_name=raw.source_name,
    )


def check_order_consignee_against_bl(
    si: RawDoc,
    bl: RawDoc,
) -> bool | None:
    """
    Special same-email rule:
    "To the Order of" on the SI is a consignee alias and should be checked
    against the BL consignee.

    Returns:
        True  -> both are present and their raw strings match after trim/casefold
        False -> both are present but differ
        None  -> one side is missing
    """
    si_value = None
    for label, value in si.fields.items():
        if clean_label(str(label)) in {"to the order of", "to order of"}:
            si_value = value
            break

    bl_value = None
    for label, value in bl.fields.items():
        if _match_field(clean_label(str(label))) == "consignee":
            bl_value = value
            break

    if not si_value or not bl_value:
        return None

    return normalize_name(si_value) == normalize_name(bl_value)
