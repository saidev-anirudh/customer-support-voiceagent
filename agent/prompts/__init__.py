"""Prompt loader. Prompts are Markdown files so they can be reviewed and edited as text."""

from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi"}


@cache
def _read(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def load_prompt(name: str, **variables: str) -> str:
    """Load ``prompts/<name>.md`` and substitute ``{placeholders}``."""
    return _read(name).format(**variables)
