"""Shared contract, agreed by all five members in Step 0. Change it only together.

  classify(email)           -> Classification      (A)  app/classify.py
  find_si_bl(email, inbox)  -> (RawDoc|None, RawDoc|None)   (B)  app/readers.py
  read_document(path)       -> RawDoc              (B; C for pdf/scan)
  decide(si, bl)            -> CompareResult       (D)  app/decide.py
  pipeline.run_email(...)   -> stored result       (E)  app/pipeline.py

RawDoc.pairs is a list of [label, value, evidence]. ORDER MATTERS: for each of the
7 fields the FIRST pair whose label maps to it wins. Reviewer corrections are
prepended to the list, so they override whatever the reader extracted.
"""
from dataclasses import dataclass, field
from typing import Optional

FIELDS = ["shipper", "consignee", "notify_party", "port_of_loading",
          "port_of_discharge", "container_count", "gross_weight_kg"]

# Labels used when a human types a value in: D's alias table must understand these.
CANONICAL_LABELS = {
    "shipper": "Shipper", "consignee": "Consignee", "notify_party": "Notify Party",
    "port_of_loading": "Port of Loading", "port_of_discharge": "Port of Discharge",
    "container_count": "Container Count", "gross_weight_kg": "Gross Weight (KG)",
}

CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")
STATUSES = ("OK", "MISMATCH", "NEEDS_REVIEW")
REVIEW_REASONS = ("wrong_doc_type", "missing_attachment", "unreadable", "missing_value")


@dataclass
class RawDoc:
    path: str = ""
    doc_type: str = "UNKNOWN"        # SI | BL | OTHER | UNKNOWN
    title: str = ""
    pairs: list = field(default_factory=list)   # [[label, value, evidence], ...]
    error: Optional[str] = None      # None | "unreadable"
    noisy: bool = False              # True when read through OCR


@dataclass
class CompareResult:
    status: str                      # OK | MISMATCH | NEEDS_REVIEW
    has_defect: bool = False
    defect_fields: list = field(default_factory=list)
    review_reason: Optional[str] = None
    diffs: list = field(default_factory=list)   # [{"field": ..., "si": ..., "bl": ...}]
    message: str = ""
