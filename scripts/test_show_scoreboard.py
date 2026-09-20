import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import show_scoreboard  # noqa: E402

BOARD = {
    "stage1": {"accuracy": 0.9, "macro_f1": 0.88, "rule_pct": None,
               "per": {"BL_COMPARISON": {"tp": 100, "fp": 5, "fn": 10}, "GENERAL": {"tp": 50, "fp": 10, "fn": 5}},
               "confusion": {"GENERAL": {"GENERAL": 50, "SI_REQUEST": 5}, "BL_COMPARISON": {"BL_COMPARISON": 100}}},
    "stage3": {"defect_precision": 0.9, "defect_recall": 0.8, "defect_f1": 0.847, "field_f1": 0.7,
               "exact_match_rate": 0.6, "doc_total": 110},
    "reliability": {"escalation_recall": 1.0, "escalation_precision": 0.9, "escalation_f1": 0.95,
                    "per_reason": {"wrong_doc_type": {"total": 5, "caught": 5}, "unreadable": {"total": 2, "caught": 1}}},
    "end_to_end": {"success": 30, "total": 50, "rate": 0.6},
    "weights": {"stage1": 0.3, "stage3": 0.2, "end_to_end": 0.5}, "final_score": 0.7,
}


class ShowScoreboardTests(unittest.TestCase):
    def test_render_has_the_numbers_a_reader_needs(self):
        text = show_scoreboard.render(BOARD, title="run 1")
        for expected in ("final_score 0.7000", "30 of 50 = 0.6000", "GENERAL -> SI_REQUEST: 5 emails",
                         "wrong_doc_type 5/5", "unreadable 1/2", "| BL_COMPARISON | 0.952 |"):
            self.assertIn(expected, text)

    def test_no_mistakes_says_none(self):
        board = {**BOARD, "stage1": {**BOARD["stage1"], "confusion": {"GENERAL": {"GENERAL": 5}}}}
        self.assertIn("- none", show_scoreboard.render(board))

    def test_prf_handles_zero(self):
        self.assertEqual(show_scoreboard.prf(0, 0, 0), (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()