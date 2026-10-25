"""Keep the call state and text-to-speech voice in sync with the caller's language."""

from __future__ import annotations

import logging

from livekit.agents import AgentSession

from state import CallState

logger = logging.getLogger("claims-agent.language")

SUPPORTED = ("en", "hi")


def to_supported(code: str | None) -> str | None:
    """Map a BCP-47 style code such as ``hi-IN`` or ``en-IN`` to ``en`` or ``hi``."""
    if not code:
        return None
    base = code.lower().split("-")[0]
    return base if base in SUPPORTED else None


def apply_language(session: AgentSession, language: str) -> bool:
    """Switch the active call language. Returns True when it changed."""
    lang = to_supported(language)
    state: CallState = session.userdata
    if lang is None or lang == state.language:
        return False
    state.language = lang  # type: ignore[assignment]
    tts = session.tts
    if tts is not None and hasattr(tts, "update_options"):
        try:
            tts.update_options(language=lang)
        except Exception:  # noqa: BLE001 - never break a call over a voice option
            logger.exception("could not update TTS language")
    logger.info("language switched to %s", lang)
    return True
