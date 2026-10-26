"""Voice pipeline: speech-to-text, language model, text-to-speech, turns, and interruptions.

Everything provider-specific lives here so it can be swapped without touching the agents.
"""

from __future__ import annotations

import logging
import os
import re

from livekit.agents import AgentSession, inference, llm, stt, vad
from livekit.agents.voice import room_io
from livekit.agents.voice.events import UserInputTranscribedEvent
from livekit.agents.voice.room_io.types import _default_text_input_cb
from livekit.plugins import cartesia, openai, sarvam

from agents.base import trigger_emergency
from language import apply_language, to_supported
from safety import is_emergency
from state import CallState

logger = logging.getLogger("claims-agent.voice")

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def build_stt() -> tuple[stt.STT, str]:
    """Return the speech-to-text engine and the matching turn-detection mode.

    Sarvam handles English, Hindi, and code-mixed speech in one stream and ends turns with
    its own voice activity detection. ``STT_PROVIDER=deepgram`` switches to Deepgram Nova-3
    multilingual through LiveKit Inference.
    """
    provider = os.getenv("STT_PROVIDER", "sarvam").lower()
    if provider == "deepgram":
        return inference.STT("deepgram/nova-3", language="multi"), "vad"
    engine = sarvam.STTRealtime(
        language="auto",
        stream_type=os.getenv("SARVAM_STREAM_TYPE", "fast"),
        mode="codemix",
        endpointing="vad",
    )
    return engine, "stt"


def build_tts() -> cartesia.TTS:
    kwargs: dict = {
        "model": os.getenv("CARTESIA_MODEL", "sonic-3"),
        "language": "en",
        "speed": float(os.getenv("CARTESIA_SPEED", "1.0")),
    }
    if voice := os.getenv("CARTESIA_VOICE_ID", "").strip():
        kwargs["voice"] = voice
    return cartesia.TTS(**kwargs)


def has_llm_credentials() -> bool:
    return bool(os.getenv("AZURE_OPENAI_MAIN_API_KEY") or os.getenv("OPENROUTER_API_KEY"))


def _supports_temperature(model: str) -> bool:
    """Reasoning deployments (gpt-5.x, o-series) reject a custom temperature."""
    return not model.lower().startswith(("gpt-5", "o1", "o3", "o4"))


def build_llm() -> llm.LLM:
    """Azure OpenAI when ``AZURE_OPENAI_MAIN_API_KEY`` is set, otherwise OpenRouter.

    The Azure v1 endpoint (``.../openai/v1``) speaks the standard OpenAI protocol, so the
    plain OpenAI client is used with ``base_url``. ``model`` is the deployment name.
    """
    if azure_key := os.getenv("AZURE_OPENAI_MAIN_API_KEY"):
        model = os.getenv("AZURE_OPENAI_MAIN_BASE_MODEL", "gpt-4.1")
        extra = {"temperature": 0.3} if _supports_temperature(model) else {}
        return openai.LLM(
            model=model,
            api_key=azure_key,
            base_url=os.environ["AZURE_OPENAI_MAIN_BASE_URL"],
            **extra,
        )
    return openai.LLM.with_openrouter(
        model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0.3,
        app_name="customer-support-voiceagent",
    )


def build_session(state: CallState, vad_model: vad.VAD | None = None) -> AgentSession:
    """Create the AgentSession with interruptions enabled and per-call state attached."""
    stt_engine, turn_detection = build_stt()
    session: AgentSession = AgentSession(
        stt=stt_engine,
        llm=build_llm(),
        tts=build_tts(),
        vad=vad_model,
        userdata=state,
        turn_handling={
            "turn_detection": turn_detection,
            "endpointing": {"min_delay": 0.3, "max_delay": 3.0},
            # Barge-in. Mode is left unset so the session uses adaptive interruption when
            # available (ignores short acknowledgements such as "okay") and VAD otherwise.
            "interruption": {"enabled": True, "min_duration": 0.4},
            # Verification attempts are counted in code, so tool calls must not run on a
            # speculative generation that may later be discarded.
            "preemptive_generation": {
                "enabled": os.getenv("PREEMPTIVE_GENERATION", "false").lower() == "true"
            },
        },
    )
    attach_language_follow(session)
    return session


def _detect(event: UserInputTranscribedEvent) -> str | None:
    """Decide the language of a final transcript, ignoring short or numeric utterances."""
    text = event.transcript.strip()
    if _DEVANAGARI.search(text):
        return "hi"
    words = re.findall(r"[^\W\d_]+", text)
    if len(words) < 3:
        return None
    return to_supported(event.language)


def attach_language_follow(session: AgentSession) -> None:
    """Follow the language the caller speaks: update the call state and the Cartesia voice."""

    @session.on("user_input_transcribed")
    def _on_transcript(event: UserInputTranscribedEvent) -> None:
        if not event.is_final:
            return
        language = _detect(event)
        if language:
            apply_language(session, language)


async def guarded_text_input(session: AgentSession, event: room_io.TextInputEvent) -> None:
    """Typed input (for example digits entered in the web UI) gets the same emergency check
    as speech. LiveKit's default handler calls ``generate_reply`` directly and would skip it."""
    if is_emergency(event.text):
        await session.interrupt()
        trigger_emergency(session)
        return
    # Typed text never produces a speech transcript, so follow the script here: Devanagari
    # means Hindi, which keeps the voice language in step with the reply language.
    if _DEVANAGARI.search(event.text):
        apply_language(session, "hi")
    await _default_text_input_cb(session, event)


def build_room_options() -> room_io.RoomOptions:
    return room_io.RoomOptions(
        text_input=room_io.TextInputOptions(text_input_cb=guarded_text_input),
        delete_room_on_close=True,
    )
