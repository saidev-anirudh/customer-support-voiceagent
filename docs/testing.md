# Testing

Tests run with pytest in `agent/`. They are layered so most of them need no credentials.

```bash
make test        # deterministic tests, no keys needed
make test-all    # also runs conversation flows against a real model
```

## Layers

| Layer | Files | Needs a model | What it proves |
| --- | --- | --- | --- |
| Normalization | `test_normalization.py` | No | Phone numbers and PINs are read correctly from digits, spoken English or Hindi words, and Devanagari digits |
| Safety | `test_safety.py` | No | Emergency phrases trigger, ordinary claim talk does not |
| State and FAQ | `test_state_and_knowledge.py` | No | Call outcome priority, unverified-name labeling, both FAQ languages for every topic |
| Auth tools | `test_auth_task.py` | No | Correct PIN, two wrong PINs, unknown numbers, malformed input, store outage, abort, and that claim tools refuse before verification |
| Emergency guard | `test_emergency_guard.py` | No | Typed and spoken emergencies share one path, reach no model, follow the call language, and stop verification |
| Post-call record | `test_postcall.py` | No | Exactly one complete record, redaction, fallback on model failure, no crash on store failure |
| Sheets backend | `test_sheets_store.py` | No | Column mapping, leading zeros, header-ordered append, raw-mode writes, error wrapping |
| Conversation flows | `test_flows.py` | Yes | The supervisor, tasks, and gates working together in text mode |

Tool bodies are exercised directly (`tests/conftest.py::call_tool`), which keeps the security-relevant logic deterministic.

## Conversation flows

`test_flows.py` drives full calls with LiveKit's `AgentSession.run` test API against the real model, with the in-memory store. It covers the happy path, the documents path, two wrong PINs, an unknown number, a representative request before verification, FAQ without verification, an attempt to skip verification, a language switch, and a final pass with LiveKit's built-in `safety_judge`, `accuracy_judge`, and `task_completion_judge`.

They need `OPENROUTER_API_KEY` (from the environment or the repo `.env`) and are skipped automatically without it. Because a language model is involved, assertions check call state and required facts rather than exact wording. If one fails intermittently, run it again before investigating, and try a stronger `LLM_MODEL`.

Each flow test takes a few seconds and uses a few model calls.

## Running a subset

```bash
cd agent
uv run pytest tests/test_auth_task.py -q
uv run pytest -m llm -k wrong_pin -q
```

## Lint

```bash
make lint
```

CI runs the same lint and the no-credentials tests on every pull request. See `.github/workflows/ci.yml`.

## Simulations (optional)

LiveKit can also run judged, goal-driven simulated callers against the agent on LiveKit Cloud:

```bash
cd agent
lk agent simulate text      # scenarios generated from the agent source
lk agent simulate audio     # through the full speech pipeline
```

Use text runs for regular checks and audio runs before a release. These are not part of CI.

## What the tests do not cover

- Audio quality, accents, noisy lines, and real speech recognition accuracy. Check these by listening, using the [scenarios](scenarios.md).
- The live Sheets API and Cartesia and Sarvam endpoints. The Sheets backend is tested against a fake spreadsheet. Verify the real connection with the snippet in [data-model.md](data-model.md#setting-up-the-spreadsheet).
