"""
contracts.py — shared data shapes across the pipeline.

Member A only relies on `Classification` here. The pipeline (E) calls
`classify(email) -> Classification` for every email, so this shape must not
change. `category` is mutable so RULE_OVERRIDES can rewrite it after the fact.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Classification:
    category: str        # BL_COMPARISON | SI_REQUEST | INVOICE_QUERY | SPAM | GENERAL
    confidence: str      # "high" | "medium" | "low"
    rule: str            # name of the rule that fired (for overrides + audit)
