from __future__ import annotations

import re
from typing import Any


_MISSING = {"", "n/a", "na", "____", "---", "--", "none", "null"}
_PUNCT_RE = re.compile(r"[^\w\s&]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
_LEADING_INT_RE = re.compile(r"^\s*(\d+)")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text.casefold() in _MISSING


def normalize_name(value: Any) -> str | None:
    """
    First line only, case/punctuation insensitive.
    LTD == LIMITED, & == AND.
    """
    if is_missing(value):
        return None

    first_line = str(value).splitlines()[0].strip().casefold()
    first_line = first_line.replace("&", " and ")
    first_line = _PUNCT_RE.sub(" ", first_line)
    first_line = _SPACE_RE.sub(" ", first_line).strip()

    tokens = []
    for token in first_line.split():
        if token == "ltd":
            token = "limited"
        tokens.append(token)

    return " ".join(tokens)


def normalize_port(value: Any) -> str | None:
    """
    Compare only the port name before the first comma.
    Any LOCODE suffix is therefore ignored.
    """
    if is_missing(value):
        return None
    text = str(value).split(",", 1)[0].strip().casefold()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_container_count(value: Any) -> int | None:
    if is_missing(value):
        return None
    match = _LEADING_INT_RE.match(str(value))
    return int(match.group(1)) if match else None


def normalize_weight(value: Any) -> float | None:
    """
    Strip common separators/units and parse the numeric amount.
    Blank / N/A / ____ are missing.
    """
    if is_missing(value):
        return None

    text = str(value).strip().casefold()
    text = text.replace(",", "").replace(" ", "")
    match = _NUMBER_RE.search(text)
    if not match:
        return None

    return float(match.group(0))


def normalize_text(value: Any) -> str | None:
    if is_missing(value):
        return None
    text = str(value).casefold()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


NORMALIZERS = {
    "shipper": normalize_name,
    "consignee": normalize_name,
    "port_of_loading": normalize_port,
    "port_of_discharge": normalize_port,
    "container_count": normalize_container_count,
    "gross_weight_kg": normalize_weight,
    "description": normalize_text,
}


def normalize_field(field: str, value: Any) -> Any:
    try:
        fn = NORMALIZERS[field]
    except KeyError as exc:
        raise KeyError(f"Unknown comparison field: {field}") from exc
    return fn(value)
