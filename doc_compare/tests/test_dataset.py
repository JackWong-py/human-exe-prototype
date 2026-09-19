from dataset import discover_attachments, group_by_case


def test_discover_and_group(tmp_path):
    case = tmp_path / "013"
    case.mkdir()
    (case / "SI.pdf").write_bytes(b"x")
    (case / "BL.pdf").write_bytes(b"x")
    (case / "ignore.json").write_text("{}")

    items = discover_attachments(tmp_path)
    grouped = group_by_case(items)

    assert len(items) == 2
    assert "013" in grouped
    assert len(grouped["013"]) == 2
