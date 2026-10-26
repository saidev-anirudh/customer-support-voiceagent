"""Typed input and spoken turns share one emergency path. Neither reaches the model."""

import types

import pytest
from livekit.agents import StopResponse, llm

from agents.auth import AuthTask
from agents.base import EmergencyGuardMixin, trigger_emergency
from safety import EMERGENCY_REPLY
from voice import guarded_text_input


class FakeSession:
    def __init__(self, state, current_agent=None):
        self.userdata = state
        self.current_agent = current_agent
        self.said: list[str] = []
        self.interrupted = False
        self.replies: list[str] = []

    def say(self, text, **kwargs):
        self.said.append(text)

    async def interrupt(self):
        self.interrupted = True

    def generate_reply(self, **kwargs):
        self.replies.append(kwargs.get("user_input", ""))


async def test_typed_emergency_speaks_fixed_reply_and_skips_the_model(state):
    session = FakeSession(state)
    await guarded_text_input(session, types.SimpleNamespace(text="my husband has chest pain"))
    assert state.emergency and state.final_outcome() == "emergency"
    assert session.said == [EMERGENCY_REPLY["en"]]
    assert session.replies == []


async def test_emergency_reply_follows_the_call_language(state):
    state.language = "hi"
    session = FakeSession(state)
    trigger_emergency(session)
    assert session.said == [EMERGENCY_REPLY["hi"]]


async def test_typed_ordinary_text_is_passed_through(state, monkeypatch):
    forwarded = []

    async def default_cb(session, event):
        forwarded.append(event.text)

    monkeypatch.setattr("voice._default_text_input_cb", default_cb)
    await guarded_text_input(FakeSession(state), types.SimpleNamespace(text="5550101001"))
    assert forwarded == ["5550101001"] and not state.emergency


async def test_emergency_stops_an_in_progress_verification(state):
    task = AuthTask(state)
    session = FakeSession(state, current_agent=task)
    trigger_emergency(session)
    assert task.done() and task._AgentTask__fut.result().status == "aborted"
    assert not state.authenticated


async def test_spoken_turn_guard_raises_stop_response(state):
    class Probe(EmergencyGuardMixin):
        def __init__(self, session):
            self.session = session

    probe = Probe(FakeSession(state))
    message = llm.ChatMessage(role="user", content=["there is a fire, he is not breathing"])
    with pytest.raises(StopResponse):
        await probe.on_user_turn_completed(llm.ChatContext(), message)
    assert state.emergency and probe.session.said

    calm = Probe(FakeSession(state))
    await calm.on_user_turn_completed(
        llm.ChatContext(), llm.ChatMessage(role="user", content=["what are your hours"])
    )
    assert calm.session.said == []


async def test_typed_devanagari_switches_the_call_to_hindi(state, monkeypatch):
    forwarded = []

    async def default_cb(session, event):
        forwarded.append(event.text)

    monkeypatch.setattr("voice._default_text_input_cb", default_cb)
    session = FakeSession(state)
    session.tts = None
    await guarded_text_input(session, types.SimpleNamespace(text="मुझे क्लेम स्टेटस चाहिए"))
    assert state.language == "hi" and forwarded == ["मुझे क्लेम स्टेटस चाहिए"]
