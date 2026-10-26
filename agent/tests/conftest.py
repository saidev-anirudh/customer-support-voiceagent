from __future__ import annotations

import os
import types
from pathlib import Path

import pytest
from dotenv import load_dotenv

from integrations import InMemoryStore
from state import CallState

# Pick up the repo-level .env when present so LLM-backed tests can run locally.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def pytest_collection_modifyitems(config, items):
    if os.getenv("AZURE_OPENAI_MAIN_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
        return
    skip = pytest.mark.skip(
        reason="no LLM credentials (AZURE_OPENAI_MAIN_API_KEY or OPENROUTER_API_KEY)"
    )
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def state(store: InMemoryStore) -> CallState:
    return CallState(store=store, room_id="test-room")


@pytest.fixture
def ctx(state: CallState):
    """Minimal stand-in for livekit's RunContext, which tool bodies use only for userdata."""
    return types.SimpleNamespace(userdata=state)


async def call_tool(tool, agent, ctx, *args, **kwargs):
    """Invoke a ``@function_tool`` body directly, without an LLM."""
    return await tool._func(agent, ctx, *args, **kwargs)
