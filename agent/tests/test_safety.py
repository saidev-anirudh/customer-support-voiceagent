import pytest

from safety import EMERGENCY_REPLY, is_emergency


@pytest.mark.parametrize(
    "text",
    [
        "My father has chest pain, please help",
        "I just had an accident",
        "someone is badly hurt",
        "the house is on fire",
        "I need an ambulance",
        "मुझे एम्बुलेंस चाहिए",
        "सीने में दर्द हो रहा है",
        "bhaiya aag lag gayi hai",
    ],
)
def test_emergencies_are_detected(text):
    assert is_emergency(text)


@pytest.mark.parametrize(
    "text",
    [
        "I want to check my claim status",
        "My car had an accident last week",
        "This is about the fire damage claim",
        "What are your office hours?",
        "आपके ऑफिस का समय क्या है",
        "",
    ],
)
def test_ordinary_claim_talk_is_not_an_emergency(text):
    assert not is_emergency(text)


def test_reply_exists_in_both_languages_and_names_the_emergency_number():
    assert set(EMERGENCY_REPLY) == {"en", "hi"}
    assert all("112" in reply for reply in EMERGENCY_REPLY.values())
