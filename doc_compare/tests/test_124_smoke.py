from models import RawDoc
from pipeline import evaluate_pair


BASE = {
    "Shipper": "ACME LTD",
    "Consignee": "BUYER LIMITED",
    "Port of Loading": "Shanghai, CNSHA",
    "Port of Discharge": "Rotterdam, NLRTM",
    "Containers": "2 x 40HC",
    "Gross Weight": "12,345 KG",
    "Description": "Frozen Beef",
}


def test_124_pairs_do_not_crash():
    # Replace this generated smoke set with the real 124 handwritten RawDoc pairs.
    pairs = []
    for i in range(124):
        si = RawDoc(doc_type="SI", fields=dict(BASE), source_name=f"{i:03d}-si")
        bl = RawDoc(doc_type="BL", fields=dict(BASE), source_name=f"{i:03d}-bl")
        pairs.append((si, bl))

    results = [evaluate_pair(si, bl) for si, bl in pairs]
    assert len(results) == 124
