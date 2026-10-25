"""Public FAQ knowledge base backed by ``kb/faq.yaml``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

FAQ_PATH = Path(__file__).parent / "kb" / "faq.yaml"
TOPICS = ("hours", "address", "new_claim", "process")


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, str]]:
    with FAQ_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def lookup_faq(topic: str, language: str = "en") -> str | None:
    """Return the FAQ answer for ``topic`` in ``language`` (falls back to English)."""
    entry = _load().get(topic)
    if not entry:
        return None
    return " ".join((entry.get(language) or entry["en"]).split())
