"""In-memory store used for tests and for running the agent without a spreadsheet."""

from __future__ import annotations

from .models import Customer, InteractionRecord, normalize_phone

SEED_CUSTOMERS: tuple[Customer, ...] = (
    Customer(
        phone="5550101001",
        name="Priya Shah",
        pin="1234",
        claim_id="CLM-1001",
        claim_status="Approved",
        status_detail="Payment of the approved amount is scheduled within 3 business days.",
        documents_needed=False,
        preferred_language="en",
    ),
    Customer(
        phone="5550101002",
        name="Amit Verma",
        pin="4321",
        claim_id="CLM-1002",
        claim_status="Pending documents",
        status_detail="The claim cannot move forward until the missing documents are received.",
        documents_needed=True,
        document_instructions=(
            "Upload a photo of the repair estimate and the signed claim form at "
            "northwind.example/claims/upload, or email them to claims@northwind.example "
            "with the claim ID CLM-1002 in the subject line. Documents are needed within 7 days."
        ),
        preferred_language="hi",
    ),
    Customer(
        phone="5550101003",
        name="Rahul Mehta",
        pin="2468",
        claim_id="CLM-1003",
        claim_status="Under review",
        status_detail="An adjuster is reviewing the claim and will respond within 5 business days.",
        documents_needed=False,
        preferred_language="en",
    ),
)


class InMemoryStore:
    def __init__(self, customers: tuple[Customer, ...] = SEED_CUSTOMERS) -> None:
        self._customers = {c.phone: c for c in customers}
        self.interactions: list[InteractionRecord] = []

    async def find_customer(self, phone: str) -> Customer | None:
        return self._customers.get(normalize_phone(phone))

    async def append_interaction(self, record: InteractionRecord) -> None:
        self.interactions.append(record)
