"""Per-call state, stored on ``AgentSession.userdata`` and shared by every agent and task.

State lives here rather than in prompts so that security decisions (is the caller
verified, how many PIN attempts remain, did an emergency occur) are made by code.
An interruption cancels speech only; nothing in this object is reset by barge-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from integrations import Customer, Store

Language = Literal["en", "hi"]

MAX_PHONE_ATTEMPTS = 2
MAX_PIN_ATTEMPTS = 2


@dataclass
class CallState:
    store: Store
    company: str = "Northwind Insurance"
    language: Language = "en"
    room_id: str = ""

    phone: str = ""
    # Account found by phone number but not yet verified. Never used for claim data.
    pending_customer: Customer | None = None
    # Set only after the PIN matches.
    customer: Customer | None = None
    authenticated: bool = False
    phone_attempts: int = 0
    pin_attempts: int = 0
    # "" until verification finishes: verified / not_found / auth_failed / unavailable
    auth_result: str = ""

    claim_discussed: bool = False
    faq_topics: list[str] = field(default_factory=list)
    escalated: bool = False
    escalation_reason: str = ""
    emergency: bool = False
    logged: bool = False

    @property
    def caller_name(self) -> str:
        if self.customer:
            return self.customer.name
        if self.pending_customer:
            return f"{self.pending_customer.name} (unverified)"
        return "Unknown"

    def final_outcome(self) -> str:
        """Derive the call outcome from facts, in priority order."""
        if self.emergency:
            return "emergency"
        if self.escalated:
            return "escalated"
        if self.auth_result == "unavailable":
            return "system_error"
        if self.auth_result == "auth_failed":
            return "auth_failed"
        if self.auth_result == "not_found":
            return "customer_not_found"
        if self.authenticated and self.claim_discussed:
            return "claim_status_provided"
        if self.faq_topics:
            return "faq_answered"
        return "abandoned" if not self.authenticated else "no_request"
