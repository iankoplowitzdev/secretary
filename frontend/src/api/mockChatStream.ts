/**
 * Local mock of a streaming chat backend.
 *
 * This simulates what a real network call (e.g. `fetch` against the future
 * streaming Lambda proxy from US-8) will eventually return: a
 * `ReadableStream<string>` of response chunks that arrive over time.
 *
 * Swapping this mock out for a real network call later is intended to be a
 * small, isolated change — see `sendChatMessage` in `./chatClient.ts`, which
 * is the only place that needs to change.
 */

const CANNED_RESPONSES = [
  "Hi there! I'm a mock assistant standing in for the real agent, " +
    'which will be wired up in a later story. ' +
    "For now I'm just streaming back some canned text so you can see " +
    'the chat UI update incrementally as chunks arrive.',
  "That's a great question. Once the real backend is connected, " +
    "I'll be able to answer questions about work history, skills, " +
    'and projects, grounded in a knowledge base. Right now this is ' +
    'simulated streaming output for local development.',
  "Thanks for trying out the chat interface! This response is being " +
    'sent word by word to exercise the streaming render path before ' +
    'a real backend exists.',
]

let responseIndex = 0

function pickCannedResponse(): string {
  const response = CANNED_RESPONSES[responseIndex % CANNED_RESPONSES.length]
  responseIndex += 1
  return response
}

function chunkText(text: string): string[] {
  // Split on whitespace boundaries but keep the trailing space so chunks
  // concatenate back into readable text.
  const words = text.split(' ')
  return words.map((word, i) => (i === words.length - 1 ? word : `${word} `))
}

export interface MockStreamOptions {
  /** Delay in ms between emitted chunks. Defaults to 40ms. */
  chunkDelayMs?: number
}

/**
 * Returns a ReadableStream<string> that emits a canned response in small
 * word-sized chunks, with a short delay between each chunk, to simulate a
 * real token-streaming backend.
 */
export function createMockChatStream(
  _message: string,
  _sessionId: string,
  options: MockStreamOptions = {},
): ReadableStream<string> {
  const { chunkDelayMs = 40 } = options
  const chunks = chunkText(pickCannedResponse())

  let cancelled = false

  return new ReadableStream<string>({
    async start(controller) {
      for (const chunk of chunks) {
        if (cancelled) break
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => setTimeout(resolve, chunkDelayMs))
        controller.enqueue(chunk)
      }
      controller.close()
    },
    cancel() {
      cancelled = true
    },
  })
}
