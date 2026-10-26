# Troubleshooting

## The agent never joins the call

- **Name mismatch.** `AGENT_NAME` in `.env` and in `web/.env.local` must be identical. The client requests that name, and only an agent registered under it will be dispatched.
- **No worker is running.** Run `make dev`, or check the deployed agent with `lk agent status` and `lk agent logs`.
- **Both a deployed agent and a local worker registered under the same name.** Stop one, or use different names.
- **Cold start.** On the free LiveKit Cloud plan a deployed agent can take 10 to 20 seconds to join after idle. See [deployment.md](deployment.md#free-plan-notes).
- **Wrong project.** The web client and the agent must use the same LiveKit project. Compare `LIVEKIT_URL` in both places.

## The page cannot get a token

- The web client needs a token source in `web/.env.local`: either `LIVEKIT_TOKEN_SERVER_ID` (turn on the development token server in your LiveKit Cloud project settings) or `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`. Restart `pnpm dev` after editing the file.

## The agent joins but never answers speech

- Check the agent logs for a Sarvam error. A `401` or a message about realtime access usually means the key is wrong or the account does not include realtime streaming.
- Switch temporarily with `STT_PROVIDER=deepgram` to confirm the rest of the pipeline works.
- Make sure the browser has microphone permission and the mic is not muted in the client.

## The agent speaks, but the voice is wrong or silent

- A bad `CARTESIA_VOICE_ID` or `CARTESIA_API_KEY` shows up as a TTS error in the logs. Use a voice id from your Cartesia library.
- If Hindi sounds off, choose a multilingual voice. Not every voice is equally good in every language.

## The language does not switch

- Automatic switching ignores short or numeric utterances on purpose. Say a full sentence, or ask "please continue in Hindi".
- Language follows the final transcript's language. If Sarvam labels a mixed sentence as English, the voice stays English.

## Phone numbers or PINs are misheard

- Ask callers to speak digit by digit, or type them into the message box.
- Spoken number words in English and Hindi and Devanagari digits are all accepted. Anything else is dropped, so an unclear utterance is treated as incomplete and re-asked.
- Try `SARVAM_STREAM_TYPE=balanced` for accuracy over latency.

## "Google Sheets is not configured" in the logs

- The agent fell back to the in-memory demo store because `GOOGLE_SHEET_ID` is empty or the key file was not found. Check `GOOGLE_SERVICE_ACCOUNT_FILE`. On LiveKit Cloud, confirm you passed `--secret-mount ./service-account.json` and that the filename matches.

## Sheet errors: permission denied, not found, quota

- **403 or "The caller does not have permission".** Share the spreadsheet with the service account's `client_email` as Editor.
- **"Unable to parse range" or worksheet not found.** The tab names must match `CUSTOMERS_TAB` and `INTERACTIONS_TAB`.
- **API not enabled.** Enable the Google Sheets API in the Google Cloud project that owns the service account.
- **429 quota.** Reduce call volume or move to a database. See [data-model.md](data-model.md#quotas-and-scale).
- During a call, a sheet failure ends verification as `unavailable` and the agent offers a callback. After a call, a write failure is logged with the full record so it can be recovered from the logs.

## No row is written after a call

- Look for `interaction recorded` or `could not write interaction record` in the agent logs.
- If the logs show the in-memory store warning, records are not being persisted. Configure Sheets.
- Rows are written when the session ends. Allow a few seconds after hanging up.

## Phone numbers and PINs lose their leading zero in the sheet

- Format the `Phone` and `PIN` columns as plain text. The agent reads them as text, but a spreadsheet may already have dropped the zero when the value was typed.

## The model ignores instructions or calls the wrong tool

- Use a stronger `LLM_MODEL` with reliable tool calling.
- Check the prompts in `agent/prompts/` and the tool descriptions in `agent/agents/supervisor.py`. Run `make test-all` to see which flow regressed.
- Remember the gates are in code: even a wrong tool call cannot reveal claim data to an unverified caller.

## Tests fail

- `make test` should pass with no keys. If it does not, run `uv sync` in `agent/`.
- Conversation-flow tests are skipped without LLM credentials (`AZURE_OPENAI_MAIN_API_KEY` or `OPENROUTER_API_KEY`). If one fails intermittently, rerun it, since it involves a real model.

## Build fails on LiveKit Cloud

- Make sure `agent/uv.lock` is committed or present, because the Dockerfile uses `uv sync --locked`.
- `lk agent logs` shows build output. Keep the build context small: `agent/.dockerignore` excludes tests, virtualenvs, and secrets.
