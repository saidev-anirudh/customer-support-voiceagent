"""Shared behavior for the supervisor and every specialist task."""

from __future__ import annotations

from livekit.agents import Agent, AgentSession, RunContext, StopResponse, llm
from livekit.agents.llm import ToolError

from safety import EMERGENCY_REPLY, is_emergency
from state import CallState


def require_auth(ctx: RunContext[CallState]) -> CallState:
    """Return the call state, or refuse the tool call if the caller is not verified.

    Every tool that touches claim data calls this first. The refusal is enforced in
    code, so it holds even if the model tries to call the tool anyway.
    """
    state = ctx.userdata
    if not (state.authenticated and state.customer):
        raise ToolError(
            "Caller is not verified. Do not share any claim information. "
            "Ask the caller to verify their identity first."
        )
    return state


def trigger_emergency(session: AgentSession) -> None:
    """Speak the fixed safety message and stop any in-progress specialist flow.

    Shared by the spoken-turn guard and the typed-input path so both behave identically.
    """
    state: CallState = session.userdata
    state.emergency = True
    session.say(EMERGENCY_REPLY[state.language], allow_interruptions=False)
    hook = getattr(session.current_agent, "on_emergency", None)
    if callable(hook):
        hook()


class EmergencyGuardMixin:
    """Intercepts emergency language before the model sees the turn.

    Mix into any ``Agent`` or ``AgentTask``. On a match it speaks a fixed, localized
    safety message, records the emergency on the call state, and skips the model turn.
    """

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        if not is_emergency(new_message.text_content or ""):
            return
        agent: Agent = self  # type: ignore[assignment]
        trigger_emergency(agent.session)
        raise StopResponse()

    def on_emergency(self) -> None:
        """Hook for tasks that must stop their own flow when an emergency is raised."""
