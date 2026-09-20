"""C's tests. Run from the repo root:

    python -m unittest tests.test_pdf_scan -v

Needs the data folder (INBOX_SOURCE, default "data"). The scan tests need the Tesseract program;
the cross-check against fixtures/rawdocs.json needs D's kit (mapping.py, normalize.py).
Nothing here calls a real model: the vision tests use a fake client.
"""
import difflib
import io
import os
import re
import shutil
import unittest
from unittest import mock

import pytesseract

from app.contracts import CANONICAL_LABELS, FIELDS
from app.inbox import get_inbox
from app.readers import common, pdf, scan

TEXT_PDFS = ["email_059", "email_160", "email_208", "email_273", "email_313",
             "email_351", "email_407", "email_411", "email_434", "email_499"]
SCANS = ["email_512", "email_513", "email_514"]
HAS_TESSERACT = shutil.which("tesseract") is not None


def read(eid, kind, fn=pdf.read_pdf):
    path = f"attachments/{eid}_{kind}.pdf"
    return fn(path, get_inbox().read_bytes(path))


def value(doc, label_regex):
    """First pair whose label matches, like the 'first pair wins' rule."""
    for label, val, _ in doc.pairs:
        if re.search(label_regex, label, re.I):
            return val
    return None


def similar(a, b):
    clean = lambda t: re.sub(r"[^A-Z0-9]", "", t.upper())          # noqa: E731
    return difflib.SequenceMatcher(None, clean(a), clean(b)).ratio()


class DocTypeTests(unittest.TestCase):
    def test_titles(self):
        cases = {"BILL OF LADING (DRAFT)": "BL", "BILL OF LADING INSTRUCTION": "SI", "SHIPPING INSTRUCTION": "SI",
                 "BL INSTRUCTION": "SI", "COMMERCIAL INVOICE": "OTHER", "PACKING LIST": "OTHER",
                 "CERTIFICATE OF ORIGIN": "OTHER", "Delivery order": "UNKNOWN", "": "UNKNOWN"}
        for title, expected in cases.items():
            with self.subTest(title):
                self.assertEqual(common.detect_doc_type(title), expected)

    def test_ocr_damaged_titles(self):
        self.assertEqual(common.detect_doc_type("BILLOF LADING (DRAFT)", fuzzy=True), "BL")
        self.assertEqual(common.detect_doc_type("SHIPPING INSTRUCTI0N", fuzzy=True), "SI")
        self.assertEqual(common.detect_doc_type("PACKING LIST", fuzzy=True), "OTHER")
        self.assertEqual(common.detect_doc_type("Delivery order", fuzzy=True), "UNKNOWN")


class TextPdfTests(unittest.TestCase):
    def test_type_and_flags(self):
        for eid in TEXT_PDFS:
            for kind, expected in (("SI", "SI"), ("BL", "BL")):
                with self.subTest(eid, kind=kind):
                    doc = read(eid, kind)
                    self.assertEqual((doc.doc_type, doc.noisy, doc.error), (expected, False, None))
                    self.assertTrue(doc.title.startswith("BILL OF LADING"))
                    self.assertTrue(doc.path.endswith(f"{eid}_{kind}.pdf"))

    def test_every_field_is_present(self):
        wanted = {"shipper": r"^shipper", "consignee": r"^consignee|to the order of", "notify": r"notify", "pol": r"load port|^pol|port of loading",
                  "pod": r"discharge|^pod", "count": r"container", "weight": r"gross"}
        for eid in TEXT_PDFS:
            for kind in ("SI", "BL"):
                doc = read(eid, kind)
                for name, rx in wanted.items():
                    with self.subTest(eid, kind=kind, field=name):
                        self.assertTrue(value(doc, rx), f"no value for {name}")

    def test_known_values(self):
        doc = read("email_059", "SI")                                  # checked against the page itself
        self.assertTrue(value(doc, r"^shipper").startswith("APRIL FINE PAPER TRADING"))
        self.assertIn(" | ON BEHALF OF VITAL SOLUTIONS PTE LTD", value(doc, r"^shipper"))   # lines joined with " | "
        self.assertTrue(value(doc, r"^consignee").startswith("BALL & DOGGETT AUSTRALIA PTY LTD"))
        self.assertTrue(value(doc, r"notify").startswith("PACIFIC OFFICE (M) SDN BHD"))
        self.assertEqual(value(doc, r"port of discharge|pod|discharge"), "FREMANTLE, AUSTRALIA")
        self.assertEqual(value(doc, r"container count|no\. of containers"), "6 x 40'HC")
        self.assertEqual(value(doc, r"gross"), "131,322 KG")

    def test_label_that_overflows_into_the_value(self):
        doc = read("email_208", "SI")            # "Notify Party/Intermediate Consignee" runs into "CERIEX"
        labels = [p[0] for p in doc.pairs]
        self.assertIn("Notify Party/Intermediate Consignee", labels)
        self.assertTrue(value(doc, r"notify").startswith("CERIEX"))

    def test_counts_and_weights_follow_the_container_table(self):
        si, bl = read("email_313", "SI"), read("email_313", "BL")      # one container row was removed from the BL
        self.assertEqual((value(si, r"containers"), value(si, r"gross")), ("5 x 40'HC", "118,270 KG"))
        self.assertEqual((value(bl, r"containers"), value(bl, r"gross")), ("4 x 40'HC", "117,770 KG"))

    def test_no_real_pdf_has_a_total_that_disagrees_with_its_rows(self):
        for eid in TEXT_PDFS:
            for kind in ("SI", "BL"):
                with self.subTest(eid, kind=kind):
                    self.assertFalse(any("container table" in p[2] for p in read(eid, kind).pairs))

    def test_printed_total_wins_over_the_roll_up(self):
        bl = read("email_351", "BL")                                    # prints "TOTAL Gross Wt (kgs): 360,415 KG"
        self.assertEqual(value(bl, r"gross"), "360,415 KG")
        self.assertFalse(any("roll-up" in p[2] for p in bl.pairs))

    @unittest.skipUnless(os.path.exists("fixtures/rawdocs.json"), "needs D's kit (fixtures/rawdocs.json)")
    def test_matches_the_independent_poppler_fixtures(self):
        import json
        from app.contracts import RawDoc
        try:
            from app.mapping import extract_fields
            from app.normalize import norm_count, norm_name, norm_port, norm_weight
        except ImportError:
            self.skipTest("needs D's mapping.py and normalize.py")

        def canon(field, v):
            if field in ("shipper", "consignee", "notify_party"):
                return norm_name(v)
            if field.startswith("port"):
                n, c, _ = norm_port(v)
                return f"{n} {c}".strip()
            return norm_count(v) if field == "container_count" else norm_weight(v)

        with open("fixtures/rawdocs.json") as fh:
            fixtures = json.load(fh)
        for eid, pair in fixtures.items():
            for kind in ("si", "bl"):
                ref = pair[kind]
                if not ref or ref["error"] or ref["noisy"] or not ref["path"].endswith(".pdf"):
                    continue
                mine = extract_fields(pdf.read_pdf(ref["path"], get_inbox().read_bytes(ref["path"])))
                theirs = extract_fields(RawDoc(**ref))
                for f in FIELDS:
                    with self.subTest(eid, kind=kind, field=f):
                        self.assertEqual(canon(f, mine[f]["value"]), canon(f, theirs[f]["value"]))


class CorruptTests(unittest.TestCase):
    def check(self, doc):
        self.assertEqual((doc.error, doc.doc_type), ("unreadable", "UNKNOWN"))
        self.assertEqual(doc.pairs[0][0], "Reader note")               # the reviewer sees why

    def test_the_two_corrupt_files(self):
        for eid in ("email_511", "email_515"):
            with self.subTest(eid):
                self.check(read(eid, "BL"))

    def test_other_bad_input_never_raises(self):
        good = get_inbox().read_bytes("attachments/email_059_SI.pdf")
        for name, data in {"empty": b"", "not a pdf": b"hello, this is text", "truncated": good[:400],
                           "header only": b"%PDF-1.5\n"}.items():
            with self.subTest(name):
                self.check(pdf.read_pdf("x.pdf", data))


@unittest.skipUnless(HAS_TESSERACT, "Tesseract is not installed")
class ScanTests(unittest.TestCase):
    # Read from the rendered pages by eye, not from the OCR output.
    TRUTH = {
        ("email_512", "SI"): {"shipper": "APRIL FAR EAST (M) SDN BHD", "consignee": "AL GURG STATIONERY LLC",
                              "notify": "AL GURG STATIONERY LLC", "loading": "NHAVA SHEVA, INDIA",
                              "discharge": "TUTICORIN, INDIA", "count": "6", "weight": "128544"},
        ("email_513", "SI"): {"shipper": "APRIL FINE PAPER TRADING", "consignee": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
                              "notify": "EAST BRIGHT FZ-LLC", "loading": "NHAVA SHEVA, INDIA",
                              "discharge": "VALPARAISO, CHILE", "count": "10", "weight": "237750"},
        ("email_514", "BL"): {"shipper": "ASIA PACIFIC PAPERBOARD TRADING PTE LTD", "consignee": "EAST BRIGHT FZ-LLC",
                              "notify": "EAST BRIGHT FZ-LLC", "loading": "NANTONG, CHINA",     # the page itself is smudged here
                              "discharge": "GDANSK, POLAND", "count": "1", "weight": "22825"},
    }
    LABEL = {"shipper": "Shipper", "consignee": "Consignee", "notify": "Notify Party", "loading": "Port of Loading",
             "discharge": "Port of Discharge", "count": "Container Count", "weight": "Gross Weight"}

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"SCAN_VISION": "off"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_scans_are_noisy_and_typed(self):
        for eid in SCANS:
            for kind in ("SI", "BL"):
                with self.subTest(eid, kind=kind):
                    doc = read(eid, kind)
                    self.assertEqual((doc.doc_type, doc.noisy, doc.error), (kind, True, None))
                    self.assertEqual({p[0] for p in doc.pairs}, {CANONICAL_LABELS[f] for f in FIELDS})

    def test_values_match_what_is_printed(self):
        for (eid, kind), truth in self.TRUTH.items():
            doc = read(eid, kind)
            for name, expected in truth.items():
                with self.subTest(eid, kind=kind, field=name):
                    got = value(doc, self.LABEL[name])
                    if name == "count":
                        self.assertEqual(re.search(r"\d+", got).group(0), expected)
                    elif name == "weight":
                        self.assertEqual(re.sub(r"[^\d]", "", got.split("KG")[0]), expected)
                    else:
                        self.assertGreaterEqual(similar(got, expected), 0.75, f"{got!r} vs {expected!r}")

    def test_evidence_keeps_the_raw_ocr_line(self):
        doc = read("email_512", "SI")
        self.assertTrue(all(p[2].startswith("OCR line") for p in doc.pairs))

    def test_missing_ocr_program_is_reported_not_hidden(self):
        with mock.patch.object(pytesseract, "image_to_data", side_effect=pytesseract.TesseractNotFoundError()):
            with self.assertRaises(scan.OcrUnavailable):
                read("email_512", "SI")


class FakeClient:
    """Stands in for the Gemini client. Records calls; returns a canned answer or raises."""

    def __init__(self, text=None, error=None):
        self.calls, self._text, self._error = 0, text, error
        self.models = self

    def generate_content(self, model, contents):
        self.calls += 1
        if self._error:
            raise self._error
        return mock.Mock(text=self._text)


VISION_JSON = """```json
{"title": "SHIPPING INSTRUCTION", "shipper": "VISION SHIPPER LTD", "consignee": "AL GURG STATIONERY LLC",
 "notify_party": null, "port_of_loading": "NHAVA SHEVA, INDIA", "port_of_discharge": "TUTICORIN, INDIA",
 "container_count": "6 x 40'HC", "gross_weight_kg": "128,544 KG"}
```"""


@unittest.skipUnless(HAS_TESSERACT, "Tesseract is not installed")
class VisionTests(unittest.TestCase):
    def run_scan(self, mode, client):
        with mock.patch.dict(os.environ, {"SCAN_VISION": mode, "GEMINI_MODEL": "test-model"}):
            path = "attachments/email_512_SI.pdf"
            return scan.read_scan(path, get_inbox().read_bytes(path), client=client)

    def test_never_called_when_ocr_is_complete_and_mode_is_fallback(self):
        client = FakeClient(VISION_JSON)
        doc = self.run_scan("fallback", client)
        self.assertEqual(client.calls, 0)
        self.assertNotIn("vision model", [p[2] for p in doc.pairs])

    def test_never_called_when_off(self):
        client = FakeClient(VISION_JSON)
        self.run_scan("off", client)
        self.assertEqual(client.calls, 0)

    def test_always_puts_the_vision_reading_first(self):
        client = FakeClient(VISION_JSON)
        doc = self.run_scan("always", client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(doc.pairs[0][:3], ["Shipper", "VISION SHIPPER LTD", "vision model"])
        self.assertTrue(doc.noisy)
        self.assertNotIn("Notify Party", [p[0] for p in doc.pairs[:6] if p[2] == "vision model"])   # null is skipped

    def test_fallback_kicks_in_when_ocr_finds_too_little(self):
        client = FakeClient(VISION_JSON)
        with mock.patch.object(scan, "_pairs_from_lines", return_value=[]):
            doc = self.run_scan("fallback", client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(value(doc, r"^shipper"), "VISION SHIPPER LTD")

    def test_vision_replaces_a_missing_ocr_program(self):
        client = FakeClient(VISION_JSON)
        with mock.patch.object(pytesseract, "image_to_data", side_effect=pytesseract.TesseractNotFoundError()):
            doc = self.run_scan("fallback", client)
        self.assertEqual((doc.doc_type, doc.noisy), ("SI", True))          # the title came from the model
        self.assertEqual(value(doc, r"^container count"), "6 x 40'HC")

    def test_a_failing_model_does_not_break_the_pipeline(self):
        client = FakeClient(error=RuntimeError("quota exceeded"))
        with mock.patch.object(scan, "_pairs_from_lines", return_value=[]):
            doc = self.run_scan("fallback", client)
        self.assertEqual(doc.pairs[-1][0], "Reader note")

    def test_a_failing_model_with_no_ocr_is_reported(self):
        client = FakeClient(error=RuntimeError("quota exceeded"))
        with mock.patch.object(pytesseract, "image_to_data", side_effect=pytesseract.TesseractNotFoundError()):
            with self.assertRaises(scan.OcrUnavailable):
                self.run_scan("fallback", client)


try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def make_pdf(title, fields, label_x=50, value_x=210, rows=()):
    """fields: [(label, [value lines], on_same_line)]. rows: [(container no, type, weight)]."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 780
    c.setFont("Helvetica-Bold", 12)
    c.drawString(label_x, y, title)
    c.setFont("Helvetica", 10)
    y -= 34
    for label, lines, same_line in fields:
        c.drawString(label_x, y, label)
        if not same_line:
            y -= 13
        for i, line in enumerate(lines):
            c.drawString(value_x, y, line)
            y -= 13
        y -= 8 if lines else 13
    if rows:
        c.drawString(label_x, y, "CONTAINER NO.")
        c.drawString(value_x + 100, y, "DESCRIPTION")
        c.drawString(value_x + 300, y, "GROSS WEIGHT (KG)")
        for no, kind, weight in rows:
            y -= 13
            c.drawString(label_x, y, no)
            c.drawString(value_x + 100, y, f"{kind} PAPER IN REAMS")
            c.drawString(value_x + 300, y, f"{weight:,}")
    c.save()
    return buf.getvalue()


@unittest.skipUnless(HAS_REPORTLAB, "reportlab is not installed (only used to build test PDFs)")
class SyntheticLayoutTests(unittest.TestCase):
    def test_a_different_column_position(self):
        data = make_pdf("SHIPPING INSTRUCTION", [
            ("Shipper", ["ACME TRADING LTD", "1 HARBOUR ROAD"], True),
            ("Consignee", ["GLOBEX CORP"], True),
            ("Port of Loading", ["SINGAPORE"], True)], label_x=40, value_x=260)
        doc = pdf.read_pdf("x.pdf", data)
        self.assertEqual(doc.doc_type, "SI")
        self.assertEqual(value(doc, r"^shipper"), "ACME TRADING LTD | 1 HARBOUR ROAD")
        self.assertEqual(value(doc, r"^consignee"), "GLOBEX CORP")
        self.assertEqual(value(doc, r"loading"), "SINGAPORE")

    def test_value_on_the_line_below_the_label(self):
        data = make_pdf("BILL OF LADING (DRAFT)", [
            ("Notify Party/Intermediate Consignee", ["INITECH LLC", "5 MAIN STREET"], False),
            ("Consignee", ["GLOBEX CORP"], True)])
        doc = pdf.read_pdf("x.pdf", data)
        self.assertEqual(doc.doc_type, "BL")
        self.assertEqual(value(doc, r"notify"), "INITECH LLC | 5 MAIN STREET")
        self.assertEqual(value(doc, r"^consignee"), "GLOBEX CORP")

    def test_a_blank_field_stays_blank_for_d(self):
        data = make_pdf("SHIPPING INSTRUCTION", [
            ("Shipper", [], True), ("Consignee", ["GLOBEX CORP", "2 SIDE ST"], True)])
        doc = pdf.read_pdf("x.pdf", data)
        self.assertEqual(value(doc, r"^shipper"), "")
        self.assertEqual(value(doc, r"^consignee"), "GLOBEX CORP | 2 SIDE ST")

    def test_roll_up_with_mixed_container_types(self):
        data = make_pdf("BILL OF LADING (DRAFT)", [("Shipper", ["ACME LTD", "ROAD"], True)],
                        rows=[("ABCD1234567", "40'HC", 20000), ("ABCD7654321", "40'HC", 21000), ("WXYZ1112223", "20'GP", 9500)])
        doc = pdf.read_pdf("x.pdf", data)
        self.assertEqual(value(doc, r"^container count"), "3 x 40'HC (mixed types)")
        self.assertEqual(value(doc, r"^gross"), "50,500")

    def test_a_printed_total_that_disagrees_with_the_rows_is_flagged(self):
        data = make_pdf("BILL OF LADING (DRAFT)", [("Shipper", ["ACME LTD", "ROAD"], True)],
                        rows=[("ABCD1234567", "40'HC", 20000), ("ABCD7654321", "40'HC", 21000)])
        # add a printed total that is wrong
        from reportlab.pdfgen import canvas as cv
        buf = io.BytesIO()
        c = cv.Canvas(buf, pagesize=A4)
        c.drawString(50, 780, "BILL OF LADING (DRAFT)")
        c.drawString(50, 740, "Shipper")
        c.drawString(210, 740, "ACME LTD")
        c.drawString(210, 727, "ROAD")
        c.drawString(50, 700, "CONTAINER NO.")
        c.drawString(50, 687, "ABCD1234567"); c.drawString(250, 687, "40'HC PAPER"); c.drawString(450, 687, "20,000")
        c.drawString(50, 674, "ABCD7654321"); c.drawString(250, 674, "40'HC PAPER"); c.drawString(450, 674, "21,000")
        c.drawString(50, 640, "TOTAL Gross Wt (kgs): 45,000 KG")
        c.save()
        doc = pdf.read_pdf("x.pdf", buf.getvalue())
        weight = next(p for p in doc.pairs if p[0].lower().startswith("total gross"))
        self.assertEqual(weight[1], "45,000 KG")
        self.assertIn("sums to 41,000", weight[2])


if __name__ == "__main__":
    unittest.main()
