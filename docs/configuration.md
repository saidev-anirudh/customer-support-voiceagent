# Configuration

All agent settings are environment variables. Locally they come from a `.env` file at the repo root (copy `.env.example`). The agent also reads an optional `agent/.env.local` that overrides it. On LiveKit Cloud they are injected as secrets. See [deployment.md](deployment.md).

## Agent variables

| Variable | Required | Secret | Purpose |
| --- | --- | --- | --- |
| `LIVEKIT_URL` | Yes (local) | No | Your project URL, `wss://<project>.livekit.cloud`. Provided automatically when deployed |
| `LIVEKIT_API_KEY` | Yes (local) | Yes | Project API key. Provided automatically when deployed |
| `LIVEKIT_API_SECRET` | Yes (local) | Yes | Project API secret. Provided automatically when deployed |
| `AGENT_NAME` | Yes | No | Name used for explicit dispatch. Must equal `AGENT_NAME` in `web/.env.local`. Default `claims-support` |
| `SARVAM_API_KEY` | Yes | Yes | Sarvam speech-to-text. Needs access to realtime streaming |
| `CARTESIA_API_KEY` | Yes | Yes | Cartesia text-to-speech |
| `CARTESIA_VOICE_ID` | Recommended | No | A multilingual Sonic voice from the Cartesia library. A default voice is used if empty |
| `CARTESIA_MODEL` | No | No | Default `sonic-3` |
| `CARTESIA_SPEED` | No | No | Speaking rate, default `1.0` |
| `AZURE_OPENAI_MAIN_API_KEY` | One LLM option | Yes | Azure OpenAI key. When set, Azure is used for the language model |
| `AZURE_OPENAI_MAIN_BASE_URL` | With Azure | No | The v1 endpoint, ending in `/openai/v1` |
| `AZURE_OPENAI_MAIN_BASE_MODEL` | With Azure | No | Deployment name, for example `gpt-4.1`. Default `gpt-4.1`. Reasoning deployments such as `gpt-5.x` are supported, and a custom temperature is skipped for them |
| `AZURE_OPENAI_MAIN_API_VERSION` | No | No | Informational. The v1 endpoint needs no `api-version` parameter |
| `OPENROUTER_API_KEY` | One LLM option | Yes | Fallback language model access, used only when no Azure key is set |
| `LLM_MODEL` | No | No | OpenRouter model that supports tool calling. Default `openai/gpt-4o-mini` |
| `GOOGLE_SHEET_ID` | For Sheets | No | The id in the spreadsheet URL |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | For Sheets | Path only | Path to the service account key. On LiveKit Cloud the file is found at `/etc/secrets/<filename>` automatically |
| `CUSTOMERS_TAB` | No | No | Default `Customers` |
| `INTERACTIONS_TAB` | No | No | Default `Interactions` |
| `COMPANY_NAME` | No | No | Name the agent uses for the company. Default `Northwind Insurance` |
| `STT_PROVIDER` | No | No | `sarvam` (default) or `deepgram` |
| `SARVAM_STREAM_TYPE` | No | No | `fast` (default), `balanced`, or `simulated`. Lower latency versus accuracy trade-off |
| `PREEMPTIVE_GENERATION` | No | No | `true` starts replies earlier. Default `false`, see [architecture.md](architecture.md) |
| `NUM_IDLE_PROCESSES` | No | No | Warm worker processes. Default `1` |

If `GOOGLE_SHEET_ID` or the key file is missing, the agent falls back to a seeded in-memory store and logs a warning.

## Web client variables

Set these in `web/.env.local`. Use one token source.

| Variable | Purpose |
| --- | --- |
| `LIVEKIT_TOKEN_SERVER_ID` | Id of the development token server. In your LiveKit Cloud project, open Settings and turn on the token server, then copy its id |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Alternative: use the included `/api/token` route |
| `AGENT_NAME` | Same value as the agent's `AGENT_NAME` |

Both token sources let any visitor request a token, so use them for development only.

## Where to get each key

- **LiveKit.** Create a project at [cloud.livekit.io](https://cloud.livekit.io). Copy the URL and an API key from Settings. Run `lk cloud auth` to link the CLI.
- **Sarvam.** Create an API key in the [Sarvam dashboard](https://dashboard.sarvam.ai). Realtime streaming must be enabled for the account.
- **Cartesia.** Create a key at [play.cartesia.ai](https://play.cartesia.ai) and pick a voice. Copy its id into `CARTESIA_VOICE_ID`.
- **Azure OpenAI.** Copy the key and the v1 endpoint from your Azure AI Foundry resource, and use the name of a deployed chat model. **OpenRouter** is the alternative: create a key at [openrouter.ai/keys](https://openrouter.ai/keys).
- **Google.** See [data-model.md](data-model.md).

## Swapping providers

Provider code is isolated in `agent/voice.py`.

- **Speech to text.** Set `STT_PROVIDER=deepgram` to use Deepgram Nova-3 multilingual through LiveKit Inference. It uses LiveKit Inference credits and needs no extra key. For another provider, change `build_stt()`.
- **Text to speech.** Change `build_tts()`. Keep the language update in `language.apply_language`, which calls `update_options(language=...)`.
- **Language model.** Azure OpenAI is used when `AZURE_OPENAI_MAIN_API_KEY` is set, otherwise OpenRouter. Change the deployment with `AZURE_OPENAI_MAIN_BASE_MODEL` or `LLM_MODEL`, or replace `build_llm()` to use another provider or a LiveKit Inference model string.
- **Storage.** Implement the `Store` protocol in `agent/integrations/models.py` (`find_customer` and `append_interaction`) and return it from `build_store()`.

## Tuning

- **Prompts.** Edit the Markdown files in `agent/prompts/`.
- **FAQ answers.** Edit `agent/kb/faq.yaml`. Each topic needs an `en` and `hi` answer.
- **Attempt limits.** `MAX_PHONE_ATTEMPTS` and `MAX_PIN_ATTEMPTS` in `agent/state.py`.
- **Emergency phrases.** `agent/safety.py`. Add tests in `agent/tests/test_safety.py` for anything you add.
- **Turn timing.** `endpointing` and `interruption` in `build_session()` in `agent/voice.py`.
