from decimal import Decimal

from arbitrage_scanner import safe_decimal


def test_safe_decimal_parses_strings():
    assert safe_decimal("$1,234.56") == Decimal("1234.56")
    assert safe_decimal("12.00") == Decimal("12.00")
    assert safe_decimal(None) is None
    assert safe_decimal("") is None
