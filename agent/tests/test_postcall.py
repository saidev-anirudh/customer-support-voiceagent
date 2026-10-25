import types

import pytest
from livekit.agents import llm

from integrations import StoreError
from postcall import (
    fallback_summary,
    format_transcript,
    parse_model_output,
    redact,
    summarize,
    write_interaction,
)


def history(*turns: tuple[str, str]) -> llm.ChatContext:
    ctx = llm.ChatContext()
    for role, text in turns:
        ctx.add_message(role=role, content=text)
    return ctx


class FakeLLM:
    def __init__(self, text=None, error=None):
        self._text, self._error = text, error

    def chat(self, *, chat_ctx):
        outer = self

        class _Stream:
            async def collect(self):
                if outer._error:
                    raise outer._error
                return types.SimpleNamespace(text=outer._text)

        return _Stream()


def test_redact_keeps_claim_ids_but_removes_phone_numbers_and_pins():
    text = "Caller 5550101001 gave PIN 4321 about claim CLM-1002"
    out = redact(text)
    assert "5550101001" not in out and "4321" not in out and "CLM-1002" in out


def test_parse_model_output_accepts_fenced_json_and_clamps_sentiment():
    raw = '```json\n{"summary": "Checked status.", "sentiment": "Positive"}\n```'
    assert parse_model_output(raw) == ("Checked status.", "positive")
    assert parse_model_output('{"summary": "x", "sentiment": "ecstatic"}') == ("x", "neutral")
    assert parse_model_output("not json") is None
    assert parse_model_output('{"summary": "", "sentiment": "neutral"}') is None


def test_format_transcript_labels_roles():
    out = format_transcript(history(("user", "hello"), ("assistant", "hi"), ("system", "secret")))
    assert out == "Caller: hello\nAgent: hi"


def test_fallback_marks_emergencies_distressed(state):
    state.emergency = True
    summary, sentiment = fallback_summary(state, "Caller: help")
    assert sentiment == "distressed" and "emergency" in summary


async def test_writes_exactly_one_complete_record(state, store):
    state.customer = state.pending_customer = store._customers["5550101001"]
    state.authenticated, state.auth_result, state.claim_discussed = True, "verified", True
    state.phone = "5550101001"
    model = FakeLLM(
        '{"summary": "Priya checked claim CLM-1001; it is approved.", "sentiment": "positive"}'
    )

    record = await write_interaction(state, history(("user", "status?")), model)
    assert await write_interaction(state, history(("user", "status?")), model) is None

    assert store.interactions == [record]
    assert record.caller_name == "Priya Shah"
    assert record.sentiment == "positive" and record.outcome == "claim_status_provided"
    assert record.summary and record.timestamp and record.room_id == "test-room"


@pytest.mark.parametrize("model", [None, FakeLLM(error=TimeoutError()), FakeLLM("garbage")])
async def test_summary_failure_still_writes_a_record(state, store, model):
    state.faq_topics.append("hours")
    record = await write_interaction(state, history(("user", "hours?")), model)
    assert len(store.interactions) == 1
    assert record.sentiment == "neutral" and record.outcome == "faq_answered" and record.summary


async def test_store_failure_does_not_raise(state):
    class Broken:
        async def append_interaction(self, record):
            raise StoreError("sheet unreachable")

    state.store = Broken()
    await write_interaction(state, history(("user", "hi")), None)
    assert state.logged


async def test_unverified_account_is_labeled_in_the_record(state, store):
    state.pending_customer = store._customers["5550101001"]
    state.auth_result = "auth_failed"
    record = await write_interaction(state, history(("user", "hi")), None)
    assert record.caller_name == "Priya Shah (unverified)" and record.outcome == "auth_failed"


async def test_summarize_without_transcript_uses_fallback(state):
    summary, sentiment = await summarize(
        state, "", FakeLLM('{"summary":"x","sentiment":"positive"}')
    )
    assert "outcome" in summary and sentiment == "neutral"
