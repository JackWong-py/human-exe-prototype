"""Tests for the Task 3 scripts. They use a fake model, so they never touch the network.

    python -m unittest tests.test_gemini_tools -v
"""
import json
import os
import shutil
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SCAN_VISION", "off")

from scripts import check_gemini, vision_vs_ocr  # noqa: E402

HAS_TESSERACT = shutil.which("tesseract") is not None

VISION_JSON = json.dumps({
    "title": "SHIPPING INSTRUCTION", "shipper": "APRIL FAR EAST (M) SDN BHD", "consignee": "AL GURG STATIONERY LLC",
    "notify_party": "AL GURG STATIONERY LLC", "port_of_loading": "NHAVA SHEVA, INDIA",
    "port_of_discharge": "TUTICORIN, INDIA", "container_count": "6 x 40'HC", "gross_weight_kg": "128,544 KG"})


class FakeClient:
    def __init__(self, text_reply="ready", vision_reply=VISION_JSON, fail=False):
        self.models = self
        self._text, self._vision, self._fail = text_reply, vision_reply, fail

    def list(self):
        return [SimpleNamespace(name=n) for n in ("models/gemini-alpha", "models/embed-x", "models/gemini-beta")]

    def generate_content(self, model, contents):
        if self._fail:
            raise RuntimeError("quota exceeded")
        return mock.Mock(text=self._vision if isinstance(contents, list) else self._text)


class CheckGeminiTests(unittest.TestCase):
    def test_lists_only_gemini_models(self):
        self.assertEqual(check_gemini.list_models(FakeClient()), ["gemini-alpha", "gemini-beta"])

    def test_text_check_passes_and_fails(self):
        self.assertTrue(check_gemini.run_checks(FakeClient(), "m")[0][1])
        self.assertFalse(check_gemini.run_checks(FakeClient(text_reply="hello"), "m")[0][1])

    def test_a_broken_client_is_reported_not_raised(self):
        results = check_gemini.run_checks(FakeClient(fail=True), "m")
        self.assertFalse(results[0][1])
        self.assertIn("RuntimeError", results[0][2])

    @unittest.skipUnless(os.path.exists("data") or os.environ.get("INBOX_SOURCE"), "needs the data folder")
    def test_vision_check_reads_seven_fields(self):
        from PIL import Image
        results = check_gemini.run_checks(FakeClient(), "m", Image.new("RGB", (10, 10)))
        self.assertEqual([ok for _, ok, _ in results], [True, True])


@unittest.skipUnless(HAS_TESSERACT, "Tesseract is not installed")
class VisionVsOcrTests(unittest.TestCase):
    def test_full_agreement_when_the_model_reads_the_page_correctly(self):
        lines = []
        summary = vision_vs_ocr.run(FakeClient(), files=[("email_512", "SI")], out=lines.append)
        self.assertEqual((summary["agree"], summary["total"]), (7, 7))
        self.assertEqual(summary["right"], {"OCR": 7, "vision": 7})
        self.assertTrue(any("agree on 7 of 7" in line for line in lines))

    def test_a_wrong_model_answer_is_counted(self):
        wrong = json.dumps({**json.loads(VISION_JSON), "gross_weight_kg": "999 KG", "shipper": "SOMEONE ELSE LTD"})
        summary = vision_vs_ocr.run(FakeClient(vision_reply=wrong), files=[("email_512", "SI")], out=lambda _: None)
        self.assertEqual(summary["agree"], 5)
        self.assertEqual(summary["right"]["vision"], 5)


if __name__ == "__main__":
    unittest.main()
