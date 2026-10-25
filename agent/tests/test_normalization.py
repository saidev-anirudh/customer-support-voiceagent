import pytest

from integrations import normalize_phone, normalize_pin


@pytest.mark.parametrize(
    "raw",
    [
        "5550101001",
        "+91 555-010-1001",
        "(555) 010 1001",
        "five five five zero one zero one zero zero one",
        "double five five zero one zero one zero zero one",
        "५५५०१०१००१",
        "पांच पांच पांच शून्य एक शून्य एक शून्य शून्य एक",
    ],
)
def test_phone_formats_normalize_to_ten_digits(raw):
    assert normalize_phone(raw) == "5550101001"


@pytest.mark.parametrize("raw", ["", "12345", "no digits here"])
def test_incomplete_phone_is_rejected(raw):
    assert normalize_phone(raw) == ""


@pytest.mark.parametrize(
    "raw", ["1234", "1 2 3 4", "one two three four", "एक दो तीन चार", "1-2-3-4"]
)
def test_pin_formats_normalize(raw):
    assert normalize_pin(raw) == "1234"
