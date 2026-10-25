"""Entry point for the claims support voice agent.

Local development:   uv run main.py dev        (connects to your LiveKit Cloud project)
Terminal test:       uv run main.py console    (talk through your microphone, no browser)
Cloud deployment:    lk agent create / lk agent deploy   (see docs/deployment.md)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import AgentServer, JobContext, JobProcess, cli
from livekit.plugins import silero

# Load the repo-level .env first, then an optional agent-local override.
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE.parent / ".env")
load_dotenv(_HERE / ".env.local", override=True)

from agents.supervisor import SupervisorAgent  # noqa: E402
from integrations import SheetsStore, build_store  # noqa: E402
from postcall import write_interaction  # noqa: E402
from state import CallState  # noqa: E402
from voice import build_llm, build_room_options, build_session  # noqa: E402

logger = logging.getLogger("claims-agent")

AGENT_NAME = os.getenv("AGENT_NAME", "claims-support")

server = AgentServer(num_idle_processes=int(os.getenv("NUM_IDLE_PROCESSES", "1")))


def prewarm(proc: JobProcess) -> None:
    """Load heavy resources once per worker process, before any call arrives."""
    proc.userdata["vad"] = silero.VAD.load()
    store = build_store()
    if isinstance(store, SheetsStore):
        try:
            store.warm()
        except Exception:  # noqa: BLE001 - lookups retry on demand
            logger.exception("could not pre-connect to Google Sheets")
    proc.userdata["store"] = store


server.setup_fnc = prewarm


async def on_session_end(ctx: JobContext) -> None:
    """Write the post-call record. Fires on any disconnect, including a closed browser tab."""
    session = ctx.primary_session
    if session is None:
        return
    state: CallState = session.userdata
    report = ctx.make_session_report()
    await write_interaction(state, report.chat_history, build_llm())


@server.rtc_session(agent_name=AGENT_NAME, on_session_end=on_session_end)
async def entrypoint(ctx: JobContext) -> None:
    state = CallState(
        store=ctx.proc.userdata.get("store") or build_store(),
        company=os.getenv("COMPANY_NAME", "Northwind Insurance"),
        room_id=ctx.room.name,
    )
    session = build_session(state, ctx.proc.userdata.get("vad"))
    await session.start(
        agent=SupervisorAgent(state), room=ctx.room, room_options=build_room_options()
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
