from mapping import check_order_consignee_against_bl, clean_label, map_doc
from models import RawDoc


def test_chinese_is_stripped_and_labels_are_case_insensitive():
    raw = RawDoc(
        doc_type="SI",
        fields={
            "发货人 SHIPPER": "ACME LTD",
            "卸货港 Port of Discharge": "Rotterdam, NLRTM",
            "NET WEIGHT 净重": "123",
        },
    )
    mapped = map_doc(raw)

    assert mapped.values["shipper"] == "ACME LTD"
    assert mapped.values["port_of_discharge"] == "Rotterdam, NLRTM"
    assert mapped.values["gross_weight_kg"] is None


def test_to_the_order_of_maps_to_consignee():
    raw = RawDoc(
        doc_type="SI",
        fields={"To the Order of": "Example Bank Ltd."},
    )
    assert map_doc(raw).values["consignee"] == "Example Bank Ltd."


def test_to_order_check_uses_name_normalization():
    si = RawDoc(doc_type="SI", fields={"To the Order of": "A & B LTD."})
    bl = RawDoc(doc_type="BL", fields={"Consignee": "A AND B LIMITED"})
    assert check_order_consignee_against_bl(si, bl) is True
