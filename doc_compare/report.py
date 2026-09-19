from __future__ import annotations

from collections.abc import Iterable

from models import DecisionStatus, RawDoc
from pipeline import evaluate_pair


def print_first_mismatches(
    pairs: Iterable[tuple[str, RawDoc, RawDoc]],
    *,
    limit: int = 30,
) -> None:
    shown = 0

    for case_id, left, right in pairs:
        result = evaluate_pair(left, right)
        if result.status is not DecisionStatus.MISMATCH:
            continue

        print(f"\n[{case_id}] MISMATCH: {', '.join(result.reasons)}")
        for diff in result.diffs:
            if diff.state.value != "different":
                continue
            ratio = f"{diff.ratio:.3f}" if diff.ratio is not None else "-"
            print(
                f"  {diff.field}: "
                f"{diff.left_raw!r} -> {diff.left_normalized!r} | "
                f"{diff.right_raw!r} -> {diff.right_normalized!r} "
                f"(ratio={ratio})"
            )

        shown += 1
        if shown >= limit:
            break
