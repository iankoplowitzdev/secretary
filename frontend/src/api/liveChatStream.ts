/**
 * Real backend transport: streams a chat response from the deployed Lambda
 * Function URL (US-8) as a ReadableStream<string>, matching the same shape
 * `mockChatStream` produces so `chatClient.ts` doesn't need to change at the
 * call site.
 *
 * The proxy forwards Bedrock AgentCore's raw SSE event stream (already
 * filtered server-side to drop internal debug dumps — see
 * lambda/proxy/index.mjs). This module does two more things the UI needs:
 *
 * 1. Extracts just the visible text deltas (`event.contentBlockDelta.delta.text`)
 *    from the structured events and ignores the rest (messageStart,
 *    contentBlockStop, metadata, etc).
 * 2. Strips the model's `<thinking>...</thinking>` preamble, which Nova Lite
 *    emits as literal visible text rather than a separate reasoning
 *    channel — showing raw chain-of-thought to site visitors would look
 *    broken. Done client-side (not via a system-prompt change) to avoid
 *    touching already-verified agent behavior for this story.
 */

const THINKING_OPEN = '<thinking>'
const THINKING_CLOSE = '</thinking>'

/** Longest suffix of `text` that is also a prefix of `marker` (0 if none). */
function longestSuffixPrefixOverlap(text: string, marker: string): number {
  const max = Math.min(text.length, marker.length - 1)
  for (let len = max; len > 0; len -= 1) {
    if (text.endsWith(marker.slice(0, len))) return len
  }
  return 0
}

/**
 * Given ALL raw text seen so far (thinking tags and all), returns the
 * visible portion with complete <thinking>...</thinking> blocks removed.
 *
 * Re-scans the full accumulated buffer on every call rather than trying to
 * process only the newest chunk in isolation — chat responses are short, so
 * this is cheap, and it's the simplest way to correctly handle a tag split
 * across two separate stream chunks (e.g. one delta ends in "<thin" and the
 * next starts with "king>"). A trailing partial match of the open tag is
 * withheld rather than shown, so a tag-in-progress never flashes to the
 * user before we know whether it's real.
 */
export function computeVisibleText(raw: string): string {
  let result = ''
  let i = 0
  while (i < raw.length) {
    const start = raw.indexOf(THINKING_OPEN, i)
    if (start === -1) {
      const remainder = raw.slice(i)
      const overlap = longestSuffixPrefixOverlap(remainder, THINKING_OPEN)
      result += remainder.slice(0, remainder.length - overlap)
      break
    }
    result += raw.slice(i, start)
    const end = raw.indexOf(THINKING_CLOSE, start)
    if (end === -1) {
      // Unclosed thinking block -- nothing more to emit until it closes.
      break
    }
    i = end + THINKING_CLOSE.length
  }
  return result
}

/** Extracts the text delta from one parsed AgentCore/Strands SSE event, if present. */
export function extractDeltaText(parsedEvent: unknown): string | null {
  if (typeof parsedEvent !== 'object' || parsedEvent === null) return null
  const event = (parsedEvent as { event?: unknown }).event
  if (typeof event !== 'object' || event === null) return null
  const contentBlockDelta = (event as { contentBlockDelta?: unknown }).contentBlockDelta
  if (typeof contentBlockDelta !== 'object' || contentBlockDelta === null) return null
  const delta = (contentBlockDelta as { delta?: unknown }).delta
  if (typeof delta !== 'object' || delta === null) return null
  const text = (delta as { text?: unknown }).text
  return typeof text === 'string' ? text : null
}

/** Splits accumulated SSE text on frame boundaries; returns [frames, remainder]. */
export function splitSseFrames(buffer: string): [string[], string] {
  const frames = buffer.split('\n\n')
  const remainder = frames.pop() ?? ''
  return [frames, remainder]
}

/** Parses one `data: ...` SSE frame and returns the delta text it carries, if any. */
export function parseSseFrame(frame: string): string | null {
  if (!frame.startsWith('data: ')) return null
  const payload = frame.slice('data: '.length)
  let parsed: unknown
  try {
    parsed = JSON.parse(payload)
  } catch {
    return null
  }
  return extractDeltaText(parsed)
}

export interface LiveChatStreamOptions {
  functionUrl: string
  fetchImpl?: typeof fetch
}

/**
 * Sends a chat message to the deployed Lambda proxy and returns a
 * ReadableStream<string> of visible response text as it streams in.
 */
export function createLiveChatStream(
  message: string,
  sessionId: string,
  { functionUrl, fetchImpl = fetch }: LiveChatStreamOptions,
): ReadableStream<string> {
  return new ReadableStream<string>({
    async start(controller) {
      let rawBuffer = ''
      let emittedLength = 0

      function handleDeltaText(text: string) {
        rawBuffer += text
        const visible = computeVisibleText(rawBuffer)
        if (visible.length > emittedLength) {
          controller.enqueue(visible.slice(emittedLength))
          emittedLength = visible.length
        }
      }

      try {
        const response = await fetchImpl(functionUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, sessionId }),
        })
        if (!response.ok || !response.body) {
          throw new Error(`Chat request failed with status ${response.status}`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let sseBuffer = ''

        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          sseBuffer += decoder.decode(value, { stream: true })
          const [frames, remainder] = splitSseFrames(sseBuffer)
          sseBuffer = remainder
          for (const frame of frames) {
            const text = parseSseFrame(frame)
            if (text) handleDeltaText(text)
          }
        }
        if (sseBuffer) {
          const text = parseSseFrame(sseBuffer)
          if (text) handleDeltaText(text)
        }
        controller.close()
      } catch (err) {
        controller.error(err)
      }
    },
  })
}
