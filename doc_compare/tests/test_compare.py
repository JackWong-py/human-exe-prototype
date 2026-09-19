from compare import compare_field
from models import CompareState


def test_noisy_fuzzy_threshold():
    diff = compare_field(
        "description",
        "Frozen Boneless Beef",
        "Frozen Boneles Beef",
        noisy=True,
    )
    assert diff.state is CompareState.EQUAL
    assert diff.ratio is not None and diff.ratio >= 0.85


def test_non_noisy_near_match_is_still_different():
    diff = compare_field(
        "description",
        "Frozen Boneless Beef",
        "Frozen Boneles Beef",
        noisy=False,
    )
    assert diff.state is CompareState.DIFFERENT
