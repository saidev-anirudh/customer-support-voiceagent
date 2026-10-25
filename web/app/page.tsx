import { App } from '@/components/app/app';

// Token source, in order of precedence: the LiveKit Cloud development token server
// (LIVEKIT_TOKEN_SERVER_ID), or the included token endpoint (LIVEKIT_URL, LIVEKIT_API_KEY,
// LIVEKIT_API_SECRET). Both are for development. See docs/deployment.md for production.
const tokenServerId = process.env.LIVEKIT_TOKEN_SERVER_ID;

export default function Page() {
  return (
    <App
      tokenServerId={tokenServerId}
      tokenEndpoint="/api/token"
      agentName={process.env.AGENT_NAME}
      isVideoInputSupported={false}
    />
  );
}
