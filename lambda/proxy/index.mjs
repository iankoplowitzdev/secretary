// Streaming proxy in front of Bedrock AgentCore Runtime (US-8).
//
// Exists so the browser never needs AWS credentials: this Lambda signs the
// InvokeAgentRuntime call with its own execution role (SigV4, handled
// automatically by the AWS SDK client -- no manual signing code needed) and
// streams the response straight back to the HTTP caller as it arrives.
//
// Response streaming via awslambda.streamifyResponse is Node.js-only on
// Lambda (confirmed against current AWS docs before choosing this runtime --
// Python requires a custom runtime or the Lambda Web Adapter).

import { randomUUID } from "node:crypto";
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";

// AgentCore's event stream interleaves two kinds of SSE frames: clean
// structured events (`data: {...}` -- a JSON object, e.g. contentBlockDelta)
// and large Python-repr debug dumps of internal Strands state re-serialized
// as a JSON *string* on every token (`data: "{...}"`). The latter re-embeds
// the whole growing conversation state each time, so a short exchange
// balloons to multiple MB and it isn't useful to a client anyway. Filter to
// objects only -- confirmed via a real invocation that this drops the
// debug dumps while keeping every real content/metadata event.
function createEventFilter() {
  let buffer = "";
  return new Transform({
    transform(chunk, _encoding, callback) {
      buffer += chunk.toString("utf-8");
      const frames = buffer.split("\n\n");
      buffer = frames.pop(); // last piece may be incomplete -- keep buffering
      for (const frame of frames) {
        if (!frame.startsWith("data: ")) continue;
        const payload = frame.slice("data: ".length);
        let parsed;
        try {
          parsed = JSON.parse(payload);
        } catch {
          // Not valid JSON -- forward as-is rather than silently dropping
          // something we don't recognize.
          this.push(frame + "\n\n");
          continue;
        }
        if (typeof parsed === "object" && parsed !== null) {
          this.push(frame + "\n\n");
        }
        // else: a JSON string (the debug dump) -- drop it.
      }
      callback();
    },
    flush(callback) {
      if (buffer.startsWith("data: ")) {
        this.push(buffer);
      }
      callback();
    },
  });
}

// Initialized outside the handler so it's reused across warm invocations.
const client = new BedrockAgentCoreClient({ region: process.env.AWS_REGION });
const AGENT_RUNTIME_ARN = process.env.AGENT_RUNTIME_ARN;

// AgentCore requires runtimeSessionId to be at least 33 characters. The
// frontend sends a real UUID (36 chars) so this is normally a no-op, but
// this is a public, unauthenticated endpoint -- never trust client input to
// already satisfy a downstream service's constraints.
function resolveSessionId(candidate) {
  if (typeof candidate === "string" && candidate.length >= 33) {
    return candidate;
  }
  return `session-${randomUUID()}`;
}

function parseBody(event) {
  if (!event.body) return {};
  const raw = event.isBase64Encoded
    ? Buffer.from(event.body, "base64").toString("utf-8")
    : event.body;
  return JSON.parse(raw);
}

export const handler = awslambda.streamifyResponse(
  async (event, responseStream, _context) => {
    let message, sessionId;
    try {
      ({ message, sessionId } = parseBody(event));
    } catch {
      const errStream = awslambda.HttpResponseStream.from(responseStream, {
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
      });
      errStream.end(JSON.stringify({ error: "Invalid JSON body" }));
      return;
    }

    if (!message || typeof message !== "string") {
      const errStream = awslambda.HttpResponseStream.from(responseStream, {
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
      });
      errStream.end(JSON.stringify({ error: "\"message\" is required" }));
      return;
    }

    const runtimeSessionId = resolveSessionId(sessionId);

    // CORS headers are NOT set here -- the Function URL's own CORS config
    // (LambdaProxyStack's FunctionUrlCorsOptions) already adds them to every
    // response automatically. Setting them here too produced a real bug:
    // duplicate Access-Control-Allow-Origin values, which browsers reject
    // outright ("The 'Access-Control-Allow-Origin' header contains multiple
    // values ... but only one is allowed") -- confirmed via a real
    // Playwright run against a live browser (curl/Node's fetch don't
    // enforce CORS, so this only broke in an actual browser).
    const httpResponseStream = awslambda.HttpResponseStream.from(
      responseStream,
      {
        statusCode: 200,
        headers: {
          "Content-Type": "text/event-stream",
        },
      },
    );

    try {
      const command = new InvokeAgentRuntimeCommand({
        agentRuntimeArn: AGENT_RUNTIME_ARN,
        runtimeSessionId,
        contentType: "application/json",
        payload: new TextEncoder().encode(JSON.stringify({ message })),
      });
      const response = await client.send(command);
      // response.response is a Node.js Readable in the Lambda runtime --
      // pipe it through the event filter as chunks arrive rather than
      // buffering the whole response.
      await pipeline(response.response, createEventFilter(), httpResponseStream);
    } catch (err) {
      // The stream's headers are already committed (200) by this point, so
      // an error here becomes a truncated stream, not a clean HTTP error
      // status -- log it for CloudWatch and end the stream gracefully
      // rather than leaking internals to the public caller.
      console.error("AgentCore invocation failed", err);
      httpResponseStream.end(
        JSON.stringify({ error: "The agent is temporarily unavailable." }),
      );
    }
  },
);
