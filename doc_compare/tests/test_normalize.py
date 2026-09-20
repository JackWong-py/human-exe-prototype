from normalize import (
    normalize_container_count,
    normalize_name,
    normalize_port,
    normalize_weight,
)


def test_name_first_line_only_and_company_aliases():
    assert normalize_name("ACME LTD\n123 Main St") == normalize_name("Acme Limited")
    assert normalize_name("A & B LTD") == normalize_name("A AND B LIMITED")


def test_port_before_comma_only():
    assert normalize_port("Rotterdam, NLRTM") == normalize_port("ROTTERDAM, NL-RTM")


def test_container_leading_integer():
    assert normalize_container_count("12 x 40HC") == 12
    assert normalize_container_count("3 containers") == 3


def test_weight_separators_and_missing_markers():
    assert normalize_weight("12,345.50 KG") == 12345.50
    assert normalize_weight("____") is None
    assert normalize_weight("N/A") is None
