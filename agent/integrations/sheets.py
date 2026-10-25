"""Google Sheets backend for customer lookups (read) and call records (write).

gspread is synchronous, so every call runs in a worker thread with a timeout and a
single retry. Failures surface as ``StoreError`` so the agent can apologize and move on
instead of crashing the session.

The sheet must contain two tabs. Header names are matched case-insensitively and
ignoring punctuation, so "Claim ID", "claim_id", and "claim id" are equivalent.
See ``docs/data-model.md`` for the full column list.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from typing import Any

import gspread

from .models import Customer, InteractionRecord, StoreError, normalize_phone

logger = logging.getLogger("claims-agent.sheets")

CUSTOMER_FIELDS = (
    "phone",
    "name",
    "pin",
    "claim_id",
    "claim_status",
    "status_detail",
    "documents_needed",
    "document_instructions",
    "preferred_language",
)

INTERACTION_FIELDS = (
    "timestamp",
    "caller_name",
    "phone",
    "summary",
    "sentiment",
    "outcome",
    "language",
    "room_id",
)


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "y", "1", "required"}


def _row_to_customer(row: dict[str, Any]) -> Customer:
    data = {_key(str(k)): str(v).strip() for k, v in row.items()}
    return Customer(
        phone=normalize_phone(data.get("phone", "")),
        name=data.get("name", ""),
        pin=data.get("pin", ""),
        claim_id=data.get("claim_id", ""),
        claim_status=data.get("claim_status", ""),
        status_detail=data.get("status_detail", ""),
        documents_needed=_truthy(data.get("documents_needed", "")),
        document_instructions=data.get("document_instructions", ""),
        preferred_language=(data.get("preferred_language", "en") or "en").lower()[:2],
    )


class SheetsStore:
    """Reads the Customers tab and appends to the Interactions tab."""

    def __init__(
        self,
        sheet_id: str,
        service_account_file: str,
        customers_tab: str = "Customers",
        interactions_tab: str = "Interactions",
        timeout: float = 8.0,
        retries: int = 1,
    ) -> None:
        self._sheet_id = sheet_id
        self._service_account_file = service_account_file
        self._customers_tab = customers_tab
        self._interactions_tab = interactions_tab
        self._timeout = timeout
        self._retries = retries
        self._spreadsheet: gspread.Spreadsheet | None = None
        self._lock = threading.Lock()

    # -- connection -------------------------------------------------------------

    def _open(self) -> gspread.Spreadsheet:
        with self._lock:
            if self._spreadsheet is None:
                client = gspread.service_account(filename=self._service_account_file)
                self._spreadsheet = client.open_by_key(self._sheet_id)
            return self._spreadsheet

    def warm(self) -> None:
        """Open the spreadsheet connection ahead of the first call (blocking)."""
        self._open()

    def _reset(self) -> None:
        with self._lock:
            self._spreadsheet = None

    async def _run(self, fn, *args):
        last: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                return await asyncio.wait_for(asyncio.to_thread(fn, *args), self._timeout)
            except Exception as exc:  # noqa: BLE001 - normalized below
                last = exc
                logger.warning("sheets call failed (attempt %d): %r", attempt + 1, exc)
                self._reset()
        raise StoreError(f"Google Sheets unavailable: {last!r}") from last

    # -- Integration 1: customer and claim lookup -------------------------------

    def _find_customer_sync(self, phone: str) -> Customer | None:
        ws = self._open().worksheet(self._customers_tab)
        rows = ws.get_all_records(numericise_ignore=["all"])
        for row in rows:
            customer = _row_to_customer(row)
            if customer.phone and customer.phone == phone:
                return customer
        return None

    async def find_customer(self, phone: str) -> Customer | None:
        normalized = normalize_phone(phone)
        if not normalized:
            return None
        return await self._run(self._find_customer_sync, normalized)

    # -- Integration 2: post-call interaction record ----------------------------

    def _append_sync(self, record: InteractionRecord) -> None:
        ws = self._open().worksheet(self._interactions_tab)
        headers = [_key(h) for h in ws.row_values(1)] or list(INTERACTION_FIELDS)
        values = {
            "timestamp": record.timestamp,
            "caller_name": record.caller_name,
            "phone": record.phone,
            "summary": record.summary,
            "sentiment": record.sentiment,
            "outcome": record.outcome,
            "language": record.language,
            "room_id": record.room_id,
        }
        # RAW prevents spreadsheet formula injection from free-text summaries.
        ws.append_row([values.get(h, "") for h in headers], value_input_option="RAW")

    async def append_interaction(self, record: InteractionRecord) -> None:
        await self._run(self._append_sync, record)
