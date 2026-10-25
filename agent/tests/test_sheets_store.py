"""SheetsStore against a fake spreadsheet, so no Google credentials are needed."""

import pytest

from integrations import InteractionRecord, StoreError
from integrations.sheets import SheetsStore

CUSTOMER_ROWS = [
    {
        "Phone": "05550101001",
        "Name": "Priya Shah",
        "PIN": "0123",
        "Claim ID": "CLM-1001",
        "Claim Status": "Approved",
        "Status Detail": "Paid soon",
        "Documents Needed": "FALSE",
        "Document Instructions": "",
        "Preferred Language": "en",
    },
    {
        "Phone": "5550101002",
        "Name": "Amit Verma",
        "PIN": "4321",
        "Claim ID": "CLM-1002",
        "Claim Status": "Pending documents",
        "Status Detail": "",
        "Documents Needed": "TRUE",
        "Document Instructions": "Upload the form",
        "Preferred Language": "HI",
    },
]


class FakeWorksheet:
    def __init__(self, rows=None, headers=None):
        self.rows, self.headers, self.appended = rows or [], headers or [], []

    def get_all_records(self, **kwargs):
        assert kwargs.get("numericise_ignore") == ["all"], "phones and PINs must stay text"
        return self.rows

    def row_values(self, n):
        return self.headers

    def append_row(self, values, value_input_option):
        self.appended.append((values, value_input_option))


class FakeSpreadsheet:
    def __init__(self, tabs):
        self.tabs = tabs

    def worksheet(self, name):
        return self.tabs[name]


@pytest.fixture
def tabs():
    return {
        "Customers": FakeWorksheet(rows=CUSTOMER_ROWS),
        "Interactions": FakeWorksheet(
            headers=["Room ID", "Timestamp", "Summary", "Caller Name", "Sentiment", "Extra"]
        ),
    }


@pytest.fixture
def sheets(tabs, monkeypatch):
    s = SheetsStore("sheet", "key.json", retries=0)
    monkeypatch.setattr(s, "_open", lambda: FakeSpreadsheet(tabs))
    return s


async def test_find_customer_maps_columns_and_normalizes(sheets):
    customer = await sheets.find_customer("+91 555 010 2002".replace("2002", "1002"))
    assert customer.name == "Amit Verma" and customer.documents_needed
    assert customer.document_instructions == "Upload the form"
    assert customer.preferred_language == "hi"


async def test_leading_zero_pin_is_preserved(sheets):
    customer = await sheets.find_customer("5550101001")
    assert customer.pin == "0123" and customer.claim_status == "Approved"


async def test_unknown_or_malformed_phone_returns_none(sheets):
    assert await sheets.find_customer("5559990000") is None
    assert await sheets.find_customer("123") is None


async def test_append_follows_sheet_header_order_and_uses_raw_mode(sheets, tabs):
    await sheets.append_interaction(
        InteractionRecord(
            caller_name="Priya Shah",
            summary="=HYPERLINK(evil)",
            sentiment="positive",
            timestamp="2026-01-01T00:00:00+00:00",
            room_id="room-1",
        )
    )
    ((values, mode),) = tabs["Interactions"].appended
    assert values == [
        "room-1",
        "2026-01-01T00:00:00+00:00",
        "=HYPERLINK(evil)",
        "Priya Shah",
        "positive",
        "",
    ]
    assert mode == "RAW"


async def test_backend_errors_become_store_errors(tabs, monkeypatch):
    s = SheetsStore("sheet", "key.json", retries=1)

    def boom():
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(s, "_open", boom)
    with pytest.raises(StoreError):
        await s.find_customer("5550101001")
