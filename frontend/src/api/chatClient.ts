/**
 * Chat transport boundary.
 *
 * This is the single seam between the chat UI and "however we actually talk
 * to the backend." Today it delegates to a local mock (`mockChatStream`) that
 * simulates a streaming response with no network involved, so `npm run dev`
 * gives a fully working conversational UI with no backend deployed.
 *
 * A future story (US-10, frontend/backend integration) swaps the body of
 * `sendChatMessage` for a real `fetch` against the streaming Lambda proxy
 * (US-8) and adapts its `Response.body` (already a ReadableStream) to the
 * same return type — no changes needed anywhere else in the app.
 */

import { createMockChatStream } from './mockChatStream'

export interface SendChatMessageRequest {
  message: string
  sessionId: string
}

/**
 * Sends a chat message and returns a stream of response text chunks.
 *
 * Currently backed by an in-browser mock. Swap this implementation for a
 * real network call (e.g. `fetch(...).then(res => adaptToStringStream(res.body))`)
 * when a real backend endpoint exists.
 */
export function sendChatMessage({
  message,
  sessionId,
}: SendChatMessageRequest): ReadableStream<string> {
  return createMockChatStream(message, sessionId)
}
