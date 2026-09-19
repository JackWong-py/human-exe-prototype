from __future__ import annotations

from decide import decide
from mapping import map_doc
from models import Decision, RawDoc


def evaluate_pair(si_raw: RawDoc, bl_raw: RawDoc) -> Decision:
    return decide(map_doc(si_raw), map_doc(bl_raw))
