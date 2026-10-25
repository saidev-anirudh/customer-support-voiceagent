"""Post-call record: summary, sentiment, and the write to the Interactions store.

Runs from the ``on_session_end`` callback, which LiveKit fires on every disconnect, so a
dropped browser tab still leaves a record. A failed summary never blocks the write.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from livekit.agents import llm

from integrations import InteractionRecord, StoreError
from state import CallState

logger = logging.getLogger("claims-agent.postcall")

SENTIMENTS = ("positive", "neutral", "negative", "distressed")
SUMMARY_TIMEOUT = 15.0
MAX_TRANSCRIPT_CHARS = 6000

_SYSTEM_PROMPT = (
    "You write post-call records for an insurance claims support line. Read the transcript and "
    "reply with strict JSON only, no prose and no code fences, using exactly these keys: "
    '"summary" is at most two plain English sentences describing what the caller wanted and what '
    'happened, even if the call was in Hindi; "sentiment" is the caller\'s emotional tone and must '
    "be one of positive, neutral, negative, distressed. Never include phone numbers, PINs, or "
    "other digit sequences in the summary."
)

_LONG_DIGITS = re.compile(r"(?<![-\w])\d{4,}(?!\w)")


def format_transcript(history: llm.ChatContext) -> str:
    lines: list[str] = []
    for msg in history.messages():
        if msg.role not in ("user", "assistant"):
            continue
        text = (msg.text_content or "").strip()
        if text:
            lines.append(f"{'Caller' if msg.role == 'user' else 'Agent'}: {text}")
    return "\n".join(lines)[-MAX_TRANSCRIPT_CHARS:]


def redact(text: str) -> str:
    """Remove long digit runs (phone numbers, PINs) while keeping ids such as CLM-1002."""
    return _LONG_DIGITS.sub("[redacted]", text)


def fallback_summary(state: CallState, transcript: str) -> tuple[str, str]:
    outcome = state.final_outcome().replace("_", " ")
    caller_lines = [
        ln[len("Caller: ") :] for ln in transcript.splitlines() if ln.startswith("Caller: ")
    ]
    excerpt = f' First request: "{caller_lines[0][:140]}"' if caller_lines else ""
    sentiment = "distressed" if state.emergency else "neutral"
    return redact(f"Call ended with outcome: {outcome}.{excerpt}"), sentiment


def parse_model_output(text: str) -> tuple[str, str] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    summary = str(data.get("summary", "")).strip()
    sentiment = str(data.get("sentiment", "")).strip().lower()
    if not summary:
        return None
    return redact(summary), sentiment if sentiment in SENTIMENTS else "neutral"


async def summarize(state: CallState, transcript: str, model: llm.LLM | None) -> tuple[str, str]:
    """Return ``(summary, sentiment)``. Falls back to a deterministic summary on any failure."""
    if model is None or not transcript:
        return fallback_summary(state, transcript)
    ctx = llm.ChatContext()
    ctx.add_message(role="system", content=_SYSTEM_PROMPT)
    ctx.add_message(
        role="user",
        content=f"Call outcome: {state.final_outcome()}\n\nTranscript:\n{transcript}",
    )
    try:
        response = await asyncio.wait_for(model.chat(chat_ctx=ctx).collect(), SUMMARY_TIMEOUT)
        parsed = parse_model_output(response.text)
        if parsed:
            return parsed
        logger.warning("summary response was not valid JSON; using fallback")
    except Exception:  # noqa: BLE001 - the record must be written regardless
        logger.exception("summary generation failed; using fallback")
    return fallback_summary(state, transcript)


async def write_interaction(
    state: CallState, history: llm.ChatContext, model: llm.LLM | None
) -> InteractionRecord | None:
    """Write exactly one interaction record for this call. Safe to call more than once."""
    if state.logged:
        return None
    state.logged = True

    transcript = format_transcript(history)
    summary, sentiment = await summarize(state, transcript, model)
    record = InteractionRecord(
        caller_name=state.caller_name,
        summary=summary,
        sentiment=sentiment,
        phone=state.phone,
        outcome=state.final_outcome(),
        language=state.language,
        room_id=state.room_id,
    )
    try:
        await state.store.append_interaction(record)
        logger.info("interaction recorded: %s / %s", record.outcome, record.sentiment)
    except StoreError:
        logger.exception("could not write interaction record; logging it instead: %s", record)
    return record
