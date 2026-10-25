"""AuthTask decisions are made in code. These tests call the tool bodies directly."""

import pytest
from livekit.agents import StopResponse
from livekit.agents.llm import ToolError

from agents.auth import AuthResult, AuthTask
from agents.base import require_auth
from integrations import StoreError
from tests.conftest import call_tool


def result_of(task: AuthTask) -> AuthResult:
    return task._AgentTask__fut.result()


async def test_correct_pin_verifies_and_returns_typed_result(state, ctx):
    task = AuthTask(state)
    msg = await call_tool(task.submit_phone, task, ctx, "5550101001")
    assert "Priya" in msg and "1234" not in msg and "CLM" not in msg
    assert not state.authenticated and state.pending_customer

    with pytest.raises(StopResponse):
        await call_tool(task.submit_pin, task, ctx, "one two three four")
    assert state.authenticated and state.auth_result == "verified"
    assert state.customer.name == "Priya Shah"
    assert result_of(task) == AuthResult("verified", "Priya")


async def test_two_wrong_pins_end_in_auth_failure(state, ctx):
    task = AuthTask(state)
    await call_tool(task.submit_phone, task, ctx, "5550101001")
    msg = await call_tool(task.submit_pin, task, ctx, "0000")
    assert "one more try" in msg and not task.done()
    with pytest.raises(StopResponse):
        await call_tool(task.submit_pin, task, ctx, "1111")
    assert not state.authenticated and state.customer is None
    assert state.auth_result == "auth_failed"
    assert result_of(task).status == "auth_failed"


async def test_two_unknown_numbers_end_in_not_found(state, ctx):
    task = AuthTask(state)
    msg = await call_tool(task.submit_phone, task, ctx, "5559998888")
    assert "try once more" in msg and not task.done()
    with pytest.raises(StopResponse):
        await call_tool(task.submit_phone, task, ctx, "5559997777")
    assert state.auth_result == "not_found" and state.pending_customer is None
    assert result_of(task).status == "not_found"


async def test_incomplete_number_does_not_use_an_attempt(state, ctx):
    task = AuthTask(state)
    msg = await call_tool(task.submit_phone, task, ctx, "555 01")
    assert "10-digit" in msg and state.phone_attempts == 0


async def test_pin_before_phone_is_refused(state, ctx):
    task = AuthTask(state)
    with pytest.raises(ToolError):
        await call_tool(task.submit_pin, task, ctx, "1234")


async def test_empty_pin_does_not_use_an_attempt(state, ctx):
    task = AuthTask(state)
    await call_tool(task.submit_phone, task, ctx, "5550101001")
    await call_tool(task.submit_pin, task, ctx, "no digits")
    assert state.pin_attempts == 0


async def test_store_outage_ends_as_unavailable(state, ctx):
    class Broken:
        async def find_customer(self, phone):
            raise StoreError("down")

    state.store = Broken()
    task = AuthTask(state)
    with pytest.raises(StopResponse):
        await call_tool(task.submit_phone, task, ctx, "5550101001")
    assert state.auth_result == "unavailable"
    assert state.final_outcome() == "system_error"


async def test_abort_verification_completes_without_authenticating(state, ctx):
    task = AuthTask(state)
    with pytest.raises(StopResponse):
        await call_tool(task.abort_verification, task, ctx, "wants a person")
    assert result_of(task).status == "aborted" and not state.authenticated


def test_claim_tools_refuse_until_verified(state, ctx):
    with pytest.raises(ToolError):
        require_auth(ctx)
    # A found-but-unverified account must not unlock claims either.
    state.pending_customer = state.store._customers["5550101001"]
    with pytest.raises(ToolError):
        require_auth(ctx)
    state.customer = state.pending_customer
    state.authenticated = True
    assert require_auth(ctx) is state
