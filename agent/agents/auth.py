"""AuthTask: phone lookup and PIN check, with the decision made in code, not by the model."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Literal

from livekit.agents import AgentTask, RunContext, StopResponse, function_tool, llm

from integrations import StoreError, normalize_phone, normalize_pin
from prompts import load_prompt
from state import MAX_PHONE_ATTEMPTS, MAX_PIN_ATTEMPTS, CallState

from .base import EmergencyGuardMixin

logger = logging.getLogger("claims-agent.auth")


@dataclass
class AuthResult:
    status: Literal["verified", "not_found", "auth_failed", "unavailable", "aborted"]
    first_name: str = ""


class AuthTask(EmergencyGuardMixin, AgentTask[AuthResult]):
    """Collects a phone number and PIN, then returns a typed verification result.

    When the flow ends (verified, failed, or aborted) the task finishes silently with
    ``StopResponse``. The supervisor then speaks the outcome, so the caller hears one
    voice and never a duplicated message.
    """

    def __init__(self, state: CallState, chat_ctx: llm.ChatContext | None = None) -> None:
        super().__init__(
            instructions=load_prompt("auth", company=state.company),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        state: CallState = self.session.userdata
        if state.pending_customer and not state.authenticated:
            hint = "Ask the caller for their account PIN."
        else:
            hint = (
                "If the caller already gave a phone number earlier in this conversation, call "
                "submit_phone with it now. Otherwise ask for the phone number linked to their "
                "account."
            )
        self.session.generate_reply(instructions=hint)

    def on_emergency(self) -> None:
        self._finish(AuthResult("aborted"))

    def _finish(self, result: AuthResult) -> None:
        if not self.done():
            self.complete(result)

    @function_tool
    async def submit_phone(self, ctx: RunContext[CallState], phone: str) -> str:
        """Look up the caller's account by phone number.

        Args:
            phone: The phone number exactly as the caller said or typed it, digits only if possible.
        """
        state = ctx.userdata
        normalized = normalize_phone(phone)
        if not normalized:
            return (
                "That is not a complete 10-digit phone number. "
                "Ask the caller to repeat it slowly, digit by digit."
            )

        state.phone_attempts += 1
        state.phone = normalized
        try:
            customer = await state.store.find_customer(normalized)
        except StoreError:
            logger.exception("customer lookup failed")
            state.auth_result = "unavailable"
            self._finish(AuthResult("unavailable"))
            raise StopResponse() from None

        if customer is None:
            if state.phone_attempts >= MAX_PHONE_ATTEMPTS:
                state.auth_result = "not_found"
                self._finish(AuthResult("not_found"))
                raise StopResponse()
            return (
                "No account was found for that number. Say so kindly and ask the caller "
                "to check the number and try once more."
            )

        state.pending_customer = customer
        return (
            f"Account found. Greet the caller by first name only ({customer.first_name}) "
            "and ask for their account PIN. Do not reveal anything else."
        )

    @function_tool
    async def submit_pin(self, ctx: RunContext[CallState], pin: str) -> str:
        """Check the caller's PIN against the account that was found.

        Args:
            pin: The PIN exactly as the caller said or typed it.
        """
        state = ctx.userdata
        customer = state.pending_customer
        if customer is None:
            raise llm.ToolError("No account has been found yet. Ask for the phone number first.")

        entered = normalize_pin(pin)
        if not entered:
            return "No PIN digits were heard. Ask the caller to say the PIN again."

        state.pin_attempts += 1
        if secrets.compare_digest(entered, normalize_pin(customer.pin)):
            state.customer = customer
            state.authenticated = True
            state.auth_result = "verified"
            self._finish(AuthResult("verified", customer.first_name))
            raise StopResponse()

        if state.pin_attempts >= MAX_PIN_ATTEMPTS:
            state.auth_result = "auth_failed"
            self._finish(AuthResult("auth_failed"))
            raise StopResponse()
        return "The PIN did not match. Say so gently and allow exactly one more try."

    @function_tool
    async def abort_verification(self, ctx: RunContext[CallState], reason: str) -> str:
        """Stop verification when the caller declines, or wants a representative or an FAQ answer.

        Args:
            reason: A few words describing why verification stopped.
        """
        logger.info("verification aborted: %s", reason)
        self._finish(AuthResult("aborted"))
        raise StopResponse()
