"""Speak-and-return specialist tasks: claims, FAQ, and representative escalation.

Each task has its own scoped instructions and a fixed set of facts assembled by code from
the verified customer record or the knowledge base. The task speaks once, in the caller's
language, then returns a typed result to the supervisor. The model only phrases the
facts; it cannot add to them.
"""

from __future__ import annotations

from dataclasses import dataclass

from livekit.agents import AgentTask, llm

from knowledge import lookup_faq
from prompts import LANGUAGE_NAMES, load_prompt
from state import CallState

from .base import EmergencyGuardMixin


@dataclass
class SpeechResult:
    """Outcome of a speak-and-return task."""

    interrupted: bool = False


class SpeakTask(EmergencyGuardMixin, AgentTask[SpeechResult]):
    """Speaks a fact-grounded answer once, then completes."""

    def __init__(
        self,
        state: CallState,
        *,
        task: str,
        facts: str,
        chat_ctx: llm.ChatContext | None = None,
    ) -> None:
        super().__init__(
            instructions=load_prompt(
                "specialist",
                company=state.company,
                language_name=LANGUAGE_NAMES[state.language],
                task=task,
                facts=facts,
            ),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        handle = self.session.generate_reply(instructions="Deliver your answer to the caller now.")
        await handle.wait_for_playout()
        if not self.done():
            self.complete(SpeechResult(interrupted=handle.interrupted))


class ClaimsTask(SpeakTask):
    """Reads out claim status and document instructions for a verified caller."""

    def __init__(self, state: CallState, chat_ctx: llm.ChatContext | None = None) -> None:
        customer = state.customer
        assert customer is not None, "ClaimsTask requires a verified customer"
        lines = [
            f"Claim id: {customer.claim_id}",
            f"Claim status: {customer.claim_status}",
        ]
        if customer.status_detail:
            lines.append(f"Status detail: {customer.status_detail}")
        if customer.documents_needed:
            lines.append("Documents are required to continue this claim.")
            lines.append(f"How to submit documents: {customer.document_instructions}")
        else:
            lines.append("No documents are required right now.")
        super().__init__(
            state,
            task=(
                "Tell the verified caller the current status of their claim. "
                "If documents are required, explain clearly how to submit them."
            ),
            facts="\n".join(f"- {line}" for line in lines),
            chat_ctx=chat_ctx,
        )


class FaqTask(SpeakTask):
    """Answers a public FAQ topic from the knowledge base."""

    def __init__(
        self, state: CallState, topic: str, chat_ctx: llm.ChatContext | None = None
    ) -> None:
        answer = lookup_faq(topic, state.language) or ""
        super().__init__(
            state,
            task="Answer the caller's general question using the approved answer below.",
            facts=f"- Approved answer: {answer}",
            chat_ctx=chat_ctx,
        )


class EscalationTask(SpeakTask):
    """Acknowledges a request for a human and records a callback."""

    def __init__(
        self, state: CallState, reason: str, chat_ctx: llm.ChatContext | None = None
    ) -> None:
        state.escalated = True
        state.escalation_reason = reason
        lines = [
            "A human representative will call the caller back within one business day.",
            "The callback is logged against this call.",
        ]
        if state.phone:
            lines.append("The callback goes to the phone number the caller gave during this call.")
        else:
            lines.append("Office hours are Monday to Friday 9 AM to 6 PM India time.")
        super().__init__(
            state,
            task=(
                "The caller asked for a human representative. Acknowledge kindly, confirm a "
                "callback has been arranged, and ask if there is anything else you can help with."
            ),
            facts="\n".join(f"- {line}" for line in lines),
            chat_ctx=chat_ctx,
        )
