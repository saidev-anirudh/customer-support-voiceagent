# Web client

Browser front end for the voice agent, based on LiveKit's MIT-licensed
[agent-starter-react](https://github.com/livekit-examples/agent-starter-react) template.
It only handles the call UI: microphone, live transcript, typed input, and call controls.
All conversation logic lives in [`../agent`](../agent).

## Run locally

```bash
cp .env.example .env.local   # fill in one token source, see below
pnpm install
pnpm dev                     # http://localhost:3000
```

Token source, pick one:

- `LIVEKIT_TOKEN_SERVER_ID`: enable the development token server in your LiveKit Cloud project settings.
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`: use the included `/api/token` route.

Both options let any visitor request a token, so they are for development only. See
[`../docs/deployment.md`](../docs/deployment.md) for production hardening.

`AGENT_NAME` must match the `AGENT_NAME` the agent registers with.

## Typed input

The message box sends text into the same conversation as speech. It is useful when a phone
number or PIN is misheard.
