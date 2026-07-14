/**
 * Chat transport boundary.
 *
 * This is the single seam between the chat UI and "however we actually talk
 * to the backend." Uses the real streaming Lambda proxy (US-8) when
 * VITE_FUNCTION_URL is configured; otherwise falls back to a local mock
 * (`mockChatStream`) so `npm run dev` still gives a fully working
 * conversational UI with no backend deployed (e.g. for pure UI iteration).
 */

import { createMockChatStream } from './mockChatStream'
import { createLiveChatStream } from './liveChatStream'

export interface SendChatMessageRequest {
  message: string
  sessionId: string
}

const FUNCTION_URL = import.meta.env.VITE_FUNCTION_URL as string | undefined

/**
 * Sends a chat message and returns a stream of response text chunks.
 *
 * Backed by the real deployed Lambda Function URL when VITE_FUNCTION_URL is
 * set (see .env.example); falls back to an in-browser mock otherwise.
 */
export function sendChatMessage({
  message,
  sessionId,
}: SendChatMessageRequest): ReadableStream<string> {
  if (FUNCTION_URL) {
    return createLiveChatStream(message, sessionId, { functionUrl: FUNCTION_URL })
  }
  return createMockChatStream(message, sessionId)
}
