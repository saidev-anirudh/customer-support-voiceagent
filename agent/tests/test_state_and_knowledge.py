from integrations import Customer
from knowledge import TOPICS, lookup_faq
from state import CallState


def make_customer() -> Customer:
    return Customer(
        phone="5550101001", name="Priya Shah", pin="1234", claim_id="C1", claim_status="Approved"
    )


def test_outcome_priority(store):
    s = CallState(store=store)
    assert s.final_outcome() == "abandoned"
    s.faq_topics.append("hours")
    assert s.final_outcome() == "faq_answered"
    s.auth_result = "not_found"
    assert s.final_outcome() == "customer_not_found"
    s.auth_result = "auth_failed"
    assert s.final_outcome() == "auth_failed"
    s.escalated = True
    assert s.final_outcome() == "escalated"
    s.emergency = True
    assert s.final_outcome() == "emergency"


def test_claim_outcome_requires_authentication(store):
    s = CallState(store=store)
    s.claim_discussed = True
    assert s.final_outcome() == "abandoned"
    s.authenticated = True
    s.customer = make_customer()
    assert s.final_outcome() == "claim_status_provided"


def test_caller_name_marks_unverified_accounts(store):
    s = CallState(store=store)
    assert s.caller_name == "Unknown"
    s.pending_customer = make_customer()
    assert s.caller_name == "Priya Shah (unverified)"
    s.customer = s.pending_customer
    assert s.caller_name == "Priya Shah"


def test_every_topic_has_both_languages():
    for topic in TOPICS:
        en, hi = lookup_faq(topic, "en"), lookup_faq(topic, "hi")
        assert en and hi and en != hi
    assert any("\u0900" <= ch <= "\u097f" for ch in lookup_faq("hours", "hi"))


def test_faq_unknown_topic_and_language_fallback():
    assert lookup_faq("pricing") is None
    assert lookup_faq("hours", "fr") == lookup_faq("hours", "en")
