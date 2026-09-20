from decide import decide
from mapping import map_doc
from models import DecisionStatus, RawDoc


BASE_FIELDS = {
    "Shipper": "ACME LTD",
    "Consignee": "BUYER LIMITED",
    "Port of Loading": "Shanghai, CNSHA",
    "Port of Discharge": "Rotterdam, NLRTM",
    "Containers": "2 x 40HC",
    "Gross Weight": "12,345 KG",
    "Description": "Frozen Beef",
}


def mk(doc_type="SI", **kwargs):
    fields = dict(BASE_FIELDS)
    fields.update(kwargs.pop("fields", {}))
    return map_doc(RawDoc(doc_type=doc_type, fields=fields, **kwargs))


def test_precedence_missing_attachment_before_everything():
    left = mk(doc_type="invoice", attachment_present=False, error="bad")
    right = mk(doc_type="BL")
    out = decide(left, right)
    assert out.status is DecisionStatus.NEEDS_REVIEW
    assert out.reasons == ["missing_attachment"]


def test_wrong_doc_type_before_unreadable():
    left = mk(doc_type="invoice", error="bad")
    right = mk(doc_type="BL")
    out = decide(left, right)
    assert out.reasons == ["wrong_doc_type"]


def test_unreadable_before_missing_value():
    left = mk(error="ocr failed", fields={"Gross Weight": ""})
    right = mk(doc_type="BL")
    out = decide(left, right)
    assert out.reasons == ["unreadable"]


def test_missing_value():
    left = mk(fields={"Gross Weight": "N/A"})
    right = mk(doc_type="BL")
    out = decide(left, right)
    assert out.status is DecisionStatus.NEEDS_REVIEW
    assert out.reasons == ["missing_value"]


def test_ok():
    left = mk()
    right = mk(doc_type="BL")
    out = decide(left, right)
    assert out.status is DecisionStatus.OK


def test_pair_must_be_one_si_and_one_bl():
    left = mk(doc_type="SI")
    right = mk(doc_type="SI")
    out = decide(left, right)
    assert out.reasons == ["wrong_doc_type"]
