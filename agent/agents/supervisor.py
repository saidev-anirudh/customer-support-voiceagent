"""SupervisorAgent: the long-lived orchestrator that routes work to specialist tasks.

The model chooses which tool to call. Everything with security or safety consequences
is enforced in code: claim access needs ``state.authenticated``, PIN checks happen inside
``AuthTask``, and emergencies are intercepted before the model sees the turn.
"""

from __future__ import annotations

import logging
from typing import Literal

from livekit.agents import Agent, RunContext, StopResponse, function_tool, llm

from knowledge import TOPICS
from language import apply_language
from prompts import load_prompt
from state import CallState

from .auth import AuthTask
from .base import EmergencyGuardMixin, require_auth
from .specialists import ClaimsTask, EscalationTask, FaqTask, SpeechResult

logger = logging.getLogger("claims-agent.supervisor")

FaqTopic = Literal["hours", "address", "new_claim", "process"]
assert set(FaqTopic.__args__) == set(TOPICS)  # type: ignore[attr-defined]


def _speech_note(result: SpeechResult) -> str:
    if result.interrupted:
        return (
            " The caller interrupted before you finished. Briefly ask if they want it repeated "
            "or have a question."
        )
    return " Ask whether there is anything else you can help with."


class SupervisorAgent(EmergencyGuardMixin, Agent):
    def __init__(self, state: CallState) -> None:
        super().__init__(instructions=load_prompt("supervisor", company=state.company))

    async def on_enter(self) -> None:
        state: CallState = self.session.userdata
        self.session.generate_reply(
            instructions=(
                f"Greet the caller warmly as the {state.company} claims support line. Say Namaste "
                "and welcome them in English and Hindi, explain in one sentence that you can help "
                "with claim status and general questions, and ask how you can help. Two sentences."
            )
        )

    # -- Identity and claims -----------------------------------------------------

    @function_tool
    async def verify_caller(self, ctx: RunContext[CallState]) -> str:
        """Verify the caller's identity with their account phone number and PIN.

        Call this before sharing any claim information. It runs a guided verification and
        returns whether the caller is verified.
        """
        state = ctx.userdata
        if state.authenticated:
            return "The caller is already verified."
        if state.auth_result in {"not_found", "auth_failed", "unavailable"}:
            raise llm.ToolError(
                "Verification already ended unsuccessfully on this call. Do not call verify_caller "
                "again. Politely offer a representative callback or the general FAQ."
            )

        result = await AuthTask(state, chat_ctx=self.chat_ctx)
        match result.status:
            case "verified":
                return (
                    f"Verified. The caller is {result.first_name}. Thank them by first name in a "
                    "few words. If they asked about their claim, call get_claim_help right away; "
                    "otherwise ask how you can help."
                )
            case "not_found":
                return (
                    "No account was found after two tries. Tell the caller kindly in one or two "
                    "sentences, then ask whether they would like a representative callback or help "
                    "with a general question. Do not call any tool until they answer."
                )
            case "auth_failed":
                return (
                    "Verification failed. Say you were unable to verify them, without explaining "
                    "why, then ask whether they would like a representative callback or help with "
                    "a general question. Do not call any tool until they answer."
                )
            case "unavailable":
                return (
                    "The account system is unavailable right now. Apologize, then ask whether they "
                    "would like a representative callback. Do not call any tool until they answer."
                )
            case _ if state.emergency:
                # The safety message has already been spoken; stay silent.
                raise StopResponse()
            case _:
                return (
                    "Verification was stopped before it finished. Handle the caller's latest "
                    "request instead."
                )

    @function_tool
    async def get_claim_help(self, ctx: RunContext[CallState]) -> str:
        """Tell a verified caller their claim status and how to submit any required documents."""
        state = require_auth(ctx)
        state.claim_discussed = True
        result = await ClaimsTask(state, chat_ctx=self.chat_ctx)
        return "Claim status delivered." + _speech_note(result)

    # -- Public information ------------------------------------------------------

    @function_tool
    async def answer_faq(self, ctx: RunContext[CallState], topic: FaqTopic) -> str:
        """Answer a general question. No verification is needed.

        Args:
            topic: hours for office hours, address for the mailing address, new_claim for how to
                start a new claim, process for the general claims process.
        """
        state = ctx.userdata
        if topic not in state.faq_topics:
            state.faq_topics.append(topic)
        result = await FaqTask(state, topic, chat_ctx=self.chat_ctx)
        return "FAQ answer delivered." + _speech_note(result)

    # -- Escalation and language -------------------------------------------------

    @function_tool
    async def request_representative(self, ctx: RunContext[CallState], reason: str) -> str:
        """Arrange a callback from a human representative. Use whenever the caller asks for a
        person, or when you cannot help.

        Args:
            reason: A few words on why the caller wants a representative.
        """
        result = await EscalationTask(ctx.userdata, reason, chat_ctx=self.chat_ctx)
        return "Representative callback arranged." + _speech_note(result)

    @function_tool
    async def switch_language(
        self, ctx: RunContext[CallState], language: Literal["en", "hi"]
    ) -> str:
        """Switch the language of the call when the caller asks for English or Hindi.

        Args:
            language: en for English, hi for Hindi.
        """
        apply_language(ctx.session, language)
        name = "Hindi" if language == "hi" else "English"
        return f"Language switched. From now on speak {name}. Confirm in one short sentence."

    # -- Ending the call ---------------------------------------------------------

    @function_tool
    async def end_call(self, ctx: RunContext[CallState]) -> str:
        """End the call after you have said goodbye and the caller needs nothing else."""
        await ctx.wait_for_playout()
        # Closing the session also deletes the room (see voice.build_room_options), which
        # disconnects the browser, and then triggers the post-call record.
        ctx.session.shutdown(drain=True)
        return "Call ended."
