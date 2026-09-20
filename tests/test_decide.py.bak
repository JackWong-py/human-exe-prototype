"""D's tests. Run from the repo root:

    python -m unittest tests.test_decide -v

The pairs in fixtures/rawdocs.json are RawDocs for every BL_COMPARISON email, so these tests
run without waiting for B and C. Add a case to GOLDEN whenever you fix a wrong decision.
"""
import json
import os
import unittest

from app.contracts import FIELDS, REVIEW_REASONS, STATUSES, RawDoc
from app.decide import compare_field, decide
from app.mapping import extract_fields, map_label
from app.normalize import (is_placeholder, norm_count, norm_name, norm_port, norm_weight)

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "rawdocs.json")

# email -> (status, review_reason, defect_fields)
GOLDEN = {
    "email_001": ("OK", None, []),                                       # everything matches
    "email_059": ("OK", None, []),                                       # text PDF, weight only in the container table
    "email_513": ("OK", None, []),                                       # scan: OCR noise is not a defect
    "email_512": ("OK", None, []),                                       # scan: "AL GUAS" vs "AL GURG"
    "email_514": ("OK", None, []),                                       # scan: "NAN TONG GHIMA" vs "NANTONG, CHINA"
    "email_013": ("MISMATCH", None, ["port_of_discharge"]),              # BL keeps the old LOCODE
    "email_025": ("MISMATCH", None, ["port_of_discharge", "container_count"]),
    "email_031": ("MISMATCH", None, ["container_count", "gross_weight_kg"]),
    "email_097": ("MISMATCH", None, ["container_count", "gross_weight_kg"]),   # 216950 vs 215,950
    "email_004": ("MISMATCH", None, ["consignee", "notify_party"]),
    "email_145": ("MISMATCH", None, ["shipper"]),                        # a different legal entity
    "email_313": ("MISMATCH", None, ["container_count", "gross_weight_kg"]),   # PDF: a container row is missing
    "email_499": ("MISMATCH", None, ["gross_weight_kg"]),
    "email_434": ("MISMATCH", None, ["port_of_discharge"]),
    "email_501": ("NEEDS_REVIEW", "wrong_doc_type", []),                 # commercial invoice in the BL slot
    "email_502": ("NEEDS_REVIEW", "wrong_doc_type", []),                 # packing list
    "email_503": ("NEEDS_REVIEW", "wrong_doc_type", []),                 # certificate of origin
    "email_506": ("NEEDS_REVIEW", "missing_attachment", []),             # nothing attached
    "email_507": ("NEEDS_REVIEW", "missing_attachment", []),             # SI only
    "email_511": ("NEEDS_REVIEW", "unreadable", []),                     # corrupt PDF
    "email_515": ("NEEDS_REVIEW", "unreadable", []),
    "email_516": ("NEEDS_REVIEW", "missing_value", []),                  # SI gross weight is N/A
    "email_519": ("NEEDS_REVIEW", "missing_value", []),                  # SI shipper and container count blank
}
MISSING = {"email_516": ["gross_weight_kg"], "email_517": ["port_of_loading", "port_of_discharge"],
           "email_518": ["port_of_discharge", "gross_weight_kg"], "email_519": ["shipper", "container_count"],
           "email_520": ["consignee"]}


def load():
    with open(FIXTURES) as fh:
        raw = json.load(fh)
    doc = lambda d: RawDoc(**d) if d else None          # noqa: E731
    return {eid: (doc(p["si"]), doc(p["bl"])) for eid, p in raw.items()}


PAIRS = load()


def doc(doc_type, pairs, noisy=False, error=None):
    return RawDoc(path="x", doc_type=doc_type, title=doc_type, pairs=[list(p) for p in pairs],
                  noisy=noisy, error=error)


ALL7 = [("Shipper", "A LTD"), ("Consignee", "B LTD"), ("Notify Party", "B LTD"),
        ("Port of Loading", "SINGAPORE"), ("Port of Discharge", "KLANG, MALAYSIA"),
        ("Container Count", "1 x 40'HC"), ("Gross Weight (KG)", "20,000 KG")]


class GoldenTests(unittest.TestCase):
    def test_golden(self):
        for eid, (status, reason, fields) in GOLDEN.items():
            with self.subTest(eid):
                r = decide(*PAIRS[eid])
                self.assertEqual((r.status, r.review_reason, r.defect_fields), (status, reason, fields))

    def test_missing_values_are_named(self):
        for eid, fields in MISSING.items():
            with self.subTest(eid):
                r = decide(*PAIRS[eid])
                self.assertEqual(r.review_reason, "missing_value")
                for f in fields:
                    self.assertIn(f, r.message)

    def test_every_fixture_gives_a_consistent_result(self):
        for eid, (si, bl) in PAIRS.items():
            with self.subTest(eid):
                r = decide(si, bl)
                self.assertIn(r.status, STATUSES)
                self.assertEqual(r.has_defect, r.status == "MISMATCH")
                if r.status == "MISMATCH":
                    self.assertTrue(r.defect_fields)
                    self.assertEqual({d["field"] for d in r.diffs}, set(r.defect_fields))
                else:
                    self.assertEqual(r.defect_fields, [])
                if r.status == "NEEDS_REVIEW":
                    self.assertIn(r.review_reason, REVIEW_REASONS)
                else:
                    self.assertIsNone(r.review_reason)

    def test_every_readable_document_has_all_seven_fields(self):
        for eid, (si, bl) in PAIRS.items():
            for d in (si, bl):
                if d is None or d.error or d.doc_type == "OTHER":
                    continue
                if eid in MISSING and d is si:      # designed blanks
                    continue
                with self.subTest(eid, doc=d.path):
                    self.assertEqual([f for f in FIELDS if f not in extract_fields(d)], [])


class MappingTests(unittest.TestCase):
    def test_labels(self):
        cases = {
            "Gross Weight毛重(KGS)": "gross_weight_kg", "Gross Wt (kgs)": "gross_weight_kg",
            "TOTAL Gross Weight (KG)": "gross_weight_kg", "NET WEIGHT": None,
            "Notify Party/Intermediate Consignee": "notify_party", "Notify": "notify_party",
            "To the Order of": "consignee", "Consignee (Non-Negotiable)": "consignee",
            "Load Port": "port_of_loading", "POL": "port_of_loading", "PORT OF LOADING": "port_of_loading",
            "Discharge Port": "port_of_discharge", "Port of Discharge (POD)": "port_of_discharge",
            "No. of Containers or Packages": "container_count", "Total Containers": "container_count",
            "Container Count": "container_count", "CONTAINER NO.": None,
            "Kinds of Packages; Description of Goods": None,       # the goods, not a count
            "Shipper (Principal or Seller) (发货人)": "shipper", "Shipper/Exporter": "shipper",
            "Export Carrier (vessel, voyage)": None, "Booking Ref": None, "HS Code": None,
        }
        for label, field in cases.items():
            with self.subTest(label):
                self.assertEqual(map_label(label), field)

    def test_first_pair_wins_so_reviewer_values_override(self):
        d = doc("BL", [("Shipper", "REVIEWER CO"), ("Shipper", "READER CO")])
        self.assertEqual(extract_fields(d)["shipper"]["value"], "REVIEWER CO")

    def test_a_later_real_value_beats_an_earlier_placeholder(self):
        d = doc("BL", [("Shipper", "N/A"), ("Shipper/Exporter", "REAL CO")])
        self.assertEqual(extract_fields(d)["shipper"]["value"], "REAL CO")


class NormalizeTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(norm_name("MOORIM SP CO., LTD | 656, GANGNAM-DAERO"), norm_name("Moorim SP Co Ltd"))
        self.assertEqual(norm_name("BALL & DOGGETT AUSTRALIA PTY LTD"), norm_name("BALL AND DOGGETT AUSTRALIA PTY LIMITED"))
        self.assertNotEqual(norm_name("APRIL FINE PAPER TRADING"), norm_name("APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"))

    def test_ports_ignore_codes_and_notes(self):
        self.assertEqual(norm_port("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)")[0], norm_port("PORT KLANG, MALAYSIA")[0])
        self.assertNotEqual(norm_port("MOMBASA, KENYA (KEMBA)")[0], norm_port("TUTICORIN, INDIA (KEMBA)")[0])

    def test_counts_and_weights(self):
        self.assertEqual([norm_count(v) for v in ("1 x 40'HC", "4X40'HC", "12", "10 x 20'FCL")], [1, 4, 12, 10])
        self.assertEqual([norm_weight(v) for v in ("21,577 KG", "216950", "341715", "128.544", "20.5 MT")],
                         [21577, 216950, 341715, 128544, 20500])

    def test_placeholders(self):
        for v in ("", "  ", "N/A", "n/a", "TBA", "TBC", "____MT", "_______ MTS", "???", "-", None):
            self.assertTrue(is_placeholder(v), repr(v))
        for v in ("SINGAPORE", "0", "1 x 40'HC", "21,577 KG"):
            self.assertFalse(is_placeholder(v), v)


class OcrTests(unittest.TestCase):
    def test_noise_is_forgiven_and_real_differences_are_not(self):
        self.assertEqual(compare_field("notify_party", "AL GURG STATIONERY LLC", "AL GUAS STATIONERY LLC", noisy=True), "same")
        self.assertEqual(compare_field("port_of_loading", "NANTONG, CHINA", "NAN TONG GHIMA", noisy=True), "same")
        self.assertEqual(compare_field("consignee", "EAST BRIGHT FZ-LLC", "UAB NOVAKOPA", noisy=True), "different")
        self.assertEqual(compare_field("shipper", "APRIL FINE PAPER TRADING",
                                       "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE", noisy=True), "unsure")

    def test_numbers_from_ocr_are_never_called_defects(self):
        self.assertEqual(compare_field("gross_weight_kg", "22,825 KG", "22,325 KG", noisy=True), "unsure")
        self.assertEqual(compare_field("gross_weight_kg", "22,825 KG", "22,325 KG", noisy=False), "different")
        self.assertEqual(compare_field("gross_weight_kg", "128,544 KG", "128.544 KG", noisy=True), "same")


class PrecedenceTests(unittest.TestCase):
    def test_order_of_review_reasons(self):
        good_si, good_bl = doc("SI", ALL7), doc("BL", ALL7)
        self.assertEqual(decide(None, doc("OTHER", [])).review_reason, "missing_attachment")
        self.assertEqual(decide(good_si, doc("OTHER", [], error="unreadable")).review_reason, "wrong_doc_type")
        self.assertEqual(decide(good_si, doc("BL", [], error="unreadable")).review_reason, "unreadable")
        self.assertEqual(decide(doc("SI", ALL7[:6]), good_bl).review_reason, "missing_value")
        self.assertEqual(decide(good_si, good_bl).status, "OK")

    def test_slots_swapped_is_a_wrong_document(self):
        self.assertEqual(decide(doc("BL", ALL7), doc("SI", ALL7)).review_reason, "wrong_doc_type")

    def test_missing_field_in_a_scan_is_a_reading_problem(self):
        r = decide(doc("SI", ALL7), doc("BL", ALL7[:6], noisy=True))
        self.assertEqual((r.status, r.review_reason), ("NEEDS_REVIEW", "unreadable"))

    def test_reviewer_corrected_values_flow_through(self):
        typed = [("Gross Weight (KG)", "21,000")] + ALL7          # reviewer's value is first, so it wins
        r = decide(doc("SI", ALL7), doc("BL", typed))
        self.assertEqual((r.status, r.defect_fields), ("MISMATCH", ["gross_weight_kg"]))


if __name__ == "__main__":
    unittest.main()

