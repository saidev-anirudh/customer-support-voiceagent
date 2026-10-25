"""Domain models and store interfaces shared by every integration backend."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


class StoreError(Exception):
    """Raised when an external system cannot be reached or returns bad data."""


_WORD_DIGITS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "शून्य": "0",
    "ज़ीरो": "0",
    "जीरो": "0",
    "एक": "1",
    "दो": "2",
    "तीन": "3",
    "चार": "4",
    "पांच": "5",
    "पाँच": "5",
    "छह": "6",
    "छः": "6",
    "छे": "6",
    "सात": "7",
    "आठ": "8",
    "नौ": "9",
    "shunya": "0",
    "ek": "1",
    "do": "2",
    "teen": "3",
    "char": "4",
    "paanch": "5",
    "panch": "5",
    "chhe": "6",
    "chhah": "6",
    "saat": "7",
    "aath": "8",
    "nau": "9",
}
_MULTIPLIERS = {"double": 2, "triple": 3, "डबल": 2, "ट्रिपल": 3}


def to_digits(raw: str) -> str:
    """Convert typed or spoken digits to ASCII digits.

    Accepts ASCII and Devanagari digits plus English and Hindi number words, including
    "double five" style repeats. Everything else is dropped.
    """
    out: list[str] = []
    repeat = 1
    # \w would split Devanagari words at combining vowel signs, so split on separators instead.
    for token in re.split(r"[\s,.\-\u2013\u2014;:()+/]+", (raw or "").lower()):
        if not token:
            continue
        if token in _MULTIPLIERS:
            repeat = _MULTIPLIERS[token]
            continue
        if token in _WORD_DIGITS:
            out.append(_WORD_DIGITS[token] * repeat)
        else:
            chunk = "".join(str(unicodedata.digit(c)) for c in token if c.isdigit())
            out.append(chunk * repeat if len(chunk) == 1 else chunk)
        repeat = 1
    return "".join(out)


def normalize_phone(raw: str) -> str:
    """Reduce any spoken or typed phone number to its last 10 digits.

    Handles separators, a leading country code, number words, and "double five" repeats.
    Returns an empty string when fewer than 10 digits remain.
    """
    digits = to_digits(raw)
    return digits[-10:] if len(digits) >= 10 else ""


def normalize_pin(raw: str) -> str:
    """Normalize a PIN so "1 2 3 4", "one two three four", and "1234" compare equal."""
    return to_digits(raw)


@dataclass(frozen=True)
class Customer:
    phone: str
    name: str
    pin: str
    claim_id: str
    claim_status: str
    status_detail: str = ""
    documents_needed: bool = False
    document_instructions: str = ""
    preferred_language: str = "en"

    @property
    def first_name(self) -> str:
        return self.name.split(" ", 1)[0] if self.name else ""


@dataclass
class InteractionRecord:
    caller_name: str
    summary: str
    sentiment: str
    phone: str = ""
    outcome: str = ""
    language: str = ""
    room_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CustomerStore(Protocol):
    async def find_customer(self, phone: str) -> Customer | None: ...


class InteractionStore(Protocol):
    async def append_interaction(self, record: InteractionRecord) -> None: ...


class Store(CustomerStore, InteractionStore, Protocol):
    """A backend that serves both integrations."""
