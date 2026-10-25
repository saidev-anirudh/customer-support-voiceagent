"""External-system integrations: customer lookup and post-call records."""

from __future__ import annotations

import logging
import os

from .memory import InMemoryStore
from .models import (
    Customer,
    InteractionRecord,
    Store,
    StoreError,
    normalize_phone,
    normalize_pin,
)
from .sheets import SheetsStore

logger = logging.getLogger("claims-agent.integrations")

__all__ = [
    "Customer",
    "InMemoryStore",
    "InteractionRecord",
    "SheetsStore",
    "Store",
    "StoreError",
    "build_store",
    "normalize_phone",
    "normalize_pin",
]


def _resolve_key_file(path: str) -> str | None:
    """Find the service-account key locally, or where LiveKit Cloud mounts file secrets."""
    if not path:
        return None
    for candidate in (path, os.path.join("/etc/secrets", os.path.basename(path))):
        if os.path.exists(candidate):
            return candidate
    return None


def build_store() -> Store:
    """Return the Sheets backend when configured, otherwise a seeded in-memory demo store."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    key_file = _resolve_key_file(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip())
    if sheet_id and key_file:
        return SheetsStore(
            sheet_id=sheet_id,
            service_account_file=key_file,
            customers_tab=os.getenv("CUSTOMERS_TAB", "Customers"),
            interactions_tab=os.getenv("INTERACTIONS_TAB", "Interactions"),
        )
    logger.warning(
        "Google Sheets is not configured; using the in-memory demo store. "
        "Call records will not persist."
    )
    return InMemoryStore()
