from attachment_reader import (
    detect_doc_type,
    extract_labeled_fields,
    rawdoc_from_attachment,
)


def test_detect_doc_type():
    assert detect_doc_type("SHIPPING INSTRUCTIONS") == "SI"
    assert detect_doc_type("BILL OF LADING") == "BL"


def test_extract_labeled_fields():
    text = """
    Shipper: ACME LTD
    Consignee: BUYER LIMITED
    Port of Loading: Shanghai, CNSHA
    Port of Discharge: Rotterdam, NLRTM
    Containers: 2 x 40HC
    Gross Weight: 12,345 KG
    Description of Goods: Frozen Beef
    """
    fields = extract_labeled_fields(text)

    assert fields["Shipper"] == "ACME LTD"
    assert fields["Consignee"] == "BUYER LIMITED"
    assert fields["Port of Discharge"] == "Rotterdam, NLRTM"
    assert fields["Gross Weight"] == "12,345 KG"


def test_rawdoc_from_txt(tmp_path):
    p = tmp_path / "013_SI.txt"
    p.write_text(
        "Shipping Instructions\n"
        "Shipper: ACME LTD\n"
        "Consignee: BUYER LTD\n",
        encoding="utf-8",
    )

    doc = rawdoc_from_attachment(p)

    assert doc.doc_type == "SI"
    assert doc.error is None
    assert doc.fields["Shipper"] == "ACME LTD"


def test_bad_extension_becomes_error(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"123")
    doc = rawdoc_from_attachment(p)
    assert doc.error is not None
