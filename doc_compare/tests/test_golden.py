from models import DecisionStatus, RawDoc
from pipeline import evaluate_pair


BASE_SI = {
    "Shipper": "ACME LTD",
    "Consignee": "BUYER LIMITED",
    "Port of Loading": "Shanghai, CNSHA",
    "Port of Discharge": "Rotterdam, NLRTM",
    "Containers": "2 x 40HC",
    "Gross Weight": "12,345 KG",
    "Description": "Frozen Beef",
}

BASE_BL = {
    "Shipper": "ACME LIMITED",
    "Consignee": "BUYER LTD",
    "Port of Loading": "Shanghai, CN-SHA",
    "Port of Discharge": "Rotterdam, NL-RTM",
    "Containers": "2 containers",
    "Gross Weight": "12345 kg",
    "Description": "Frozen Beef",
}


def test_013_flags_port_of_discharge():
    si = RawDoc(doc_type="SI", fields=BASE_SI)
    bl_fields = dict(BASE_BL)
    bl_fields["Port of Discharge"] = "Hamburg, DEHAM"
    bl = RawDoc(doc_type="BL", fields=bl_fields)

    out = evaluate_pair(si, bl)

    assert out.status is DecisionStatus.MISMATCH
    assert out.reasons == ["port_of_discharge"]


def test_097_flags_gross_weight_kg():
    si = RawDoc(doc_type="SI", fields=BASE_SI)
    bl_fields = dict(BASE_BL)
    bl_fields["Gross Weight"] = "13,000 KG"
    bl = RawDoc(doc_type="BL", fields=bl_fields)

    out = evaluate_pair(si, bl)

    assert out.status is DecisionStatus.MISMATCH
    assert out.reasons == ["gross_weight_kg"]


def test_516_returns_missing_value():
    si_fields = dict(BASE_SI)
    si_fields["Gross Weight"] = "____"

    si = RawDoc(doc_type="SI", fields=si_fields)
    bl = RawDoc(doc_type="BL", fields=BASE_BL)

    out = evaluate_pair(si, bl)

    assert out.status is DecisionStatus.NEEDS_REVIEW
    assert out.reasons == ["missing_value"]
