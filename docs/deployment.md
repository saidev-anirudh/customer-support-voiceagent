# Deployment

The agent is deployed to [LiveKit Cloud](https://docs.livekit.io/deploy/agents/) with the LiveKit CLI. The web client is a separate Next.js app that you can run locally or host anywhere.

## Prerequisites

- A LiveKit Cloud project and the CLI: `brew install livekit-cli`, then `lk cloud auth`.
- Keys filled in `.env` (see [configuration.md](configuration.md)).
- The service account key at `agent/service-account.json` if you use Google Sheets (see [data-model.md](data-model.md)).

## First deploy

Run from the `agent/` directory:

```bash
cd agent
lk agent create \
  --secrets-file ../.env \
  --ignore-empty-secrets \
  --secret-mount ./service-account.json
```

What this does:

- Registers the agent with your project and writes `livekit.toml` (project and agent ids). Commit it only if you are comfortable sharing those ids.
- Builds the image from [`agent/Dockerfile`](../agent/Dockerfile) and deploys it. The build downloads the voice activity and turn-detection model files, so first calls are not slow.
- Injects every non-empty value in `.env` as an environment variable (`--ignore-empty-secrets` skips blank optional settings). LiveKit credentials are skipped because the platform provides them.
- Mounts the key file at `/etc/secrets/service-account.json`. The agent finds it there automatically, so the same `GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json` works locally and in the cloud.

The agent registers under `AGENT_NAME` (default `claims-support`). The web client requests that name when it joins, which is how the call reaches this agent.

## Updating

| Task | Command |
| --- | --- |
| Deploy new code | `make deploy` (runs `lk agent deploy` in `agent/`) |
| Change secrets | `make update-secrets`, which triggers a rolling restart |
| Tail logs | `lk agent logs` |
| List versions | `lk agent versions` |
| Status | `lk agent status` |
| Roll back | `lk agent rollback` (paid plans) |

## Local development against the cloud project

```bash
make dev        # agent worker with hot reload, connects to your project
make web        # browser client at http://localhost:3000
```

For a quick check with no browser, `make console` runs a terminal conversation. It needs the speech and model keys but not a LiveKit server.

A deployed agent and a local `dev` worker with the same `AGENT_NAME` both register. Stop one while testing the other, or give the local worker a different `AGENT_NAME` and set the same name in `web/.env.local`.

## Running the web client

```bash
cd web
cp .env.example .env.local     # set the token source and AGENT_NAME
pnpm install
pnpm dev                       # development
pnpm build && pnpm start       # production build
```

For a hosted client (for example Vercel), set the same environment variables and replace the development token source as described below.

## Free plan notes

The free LiveKit Cloud plan is enough to run this project. Know its limits:

- **Cold starts.** After all sessions end, a free-plan agent can scale to zero. The next call can take 10 to 20 seconds to get an agent. Connect once a few minutes before a live demo, or run `make dev` locally. Paid plans keep agents warm.
- **Session minutes and concurrency.** 1,000 agent session minutes a month and 5 concurrent sessions at the time of writing. Check the [current limits](https://docs.livekit.io/deploy/admin/quotas-and-limits/).
- **One production deployment** and no non-production deployments.
- **Inference credits** are small. This project uses your own Sarvam, Cartesia, and OpenRouter keys, so credits are only used if you set `STT_PROVIDER=deepgram`.
- Adaptive interruption and the turn-detection model are included for agents hosted on LiveKit Cloud.

## Observability

LiveKit Cloud's Agent Insights shows each session: turn-by-turn transcript, tool calls, traces, logs, and audio. The `Room ID` column in the Interactions sheet is the session's room name, so you can jump from a call record to its full timeline.

## Production hardening

This repo is a working reference. Before real customer traffic:

- **Token endpoint.** Replace the development token server and the included `/api/token` route with your own authenticated endpoint that mints short-lived, scoped tokens.
- **Storage.** Move from Google Sheets to a database. Keep the `Store` interface so the agent code does not change. Add indexes on phone number.
- **Credentials.** Store PINs as salted hashes (or replace PIN with a stronger factor such as an OTP). Keep the Google key out of the repo and rotate it.
- **Abuse limits.** Add per-phone and per-caller rate limits across calls. The current attempt limits are per call.
- **Privacy.** Decide retention for transcripts, audio recordings, and summaries. Insights data is kept for a limited time by default. The summary already redacts long digit runs, and you may want to extend redaction.
- **Live transfer.** Escalation records a callback. To transfer live, add LiveKit telephony and a warm-transfer task.
- **Warm capacity.** Use a paid plan so agents do not cold start, and tune `NUM_IDLE_PROCESSES`.
- **Telephony.** To take real phone calls, attach a LiveKit phone number or SIP trunk to the same agent. The conversation logic does not change.
- **Monitoring.** Set up a log drain and alerts for sheet errors, summary failures, and verification failure rates.
- **Safety review.** Have the emergency phrase list and wording reviewed for your regions and languages.

## Scaling notes

Each call is one agent session, and LiveKit Cloud scales workers with demand on paid plans. The agent holds no cross-call state, so replicas are interchangeable. The shared bottleneck is the external store, which is why moving off Sheets is the first scaling step.
