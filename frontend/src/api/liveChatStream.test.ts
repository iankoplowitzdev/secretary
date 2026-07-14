import { describe, expect, it, vi } from 'vitest'
import {
  computeVisibleText,
  createLiveChatStream,
  extractDeltaText,
  parseSseFrame,
  splitSseFrames,
} from './liveChatStream'

describe('computeVisibleText', () => {
  it('passes plain text through unchanged', () => {
    expect(computeVisibleText('Hello there')).toBe('Hello there')
  })

  it('strips a complete thinking block', () => {
    expect(computeVisibleText('<thinking>internal notes</thinking>Real answer')).toBe(
      'Real answer',
    )
  })

  it('strips a thinking block in the middle of text', () => {
    expect(
      computeVisibleText('Before <thinking>hidden</thinking> after'),
    ).toBe('Before  after')
  })

  it('withholds an unclosed thinking block entirely', () => {
    expect(computeVisibleText('Answer so far <thinking>still going')).toBe(
      'Answer so far ',
    )
  })

  it('withholds a partial open-tag prefix so it never flashes to the user', () => {
    expect(computeVisibleText('Hello <thin')).toBe('Hello ')
    expect(computeVisibleText('Hello <')).toBe('Hello ')
  })

  it('resolves once the rest of the tag arrives (simulating incremental streaming)', () => {
    // Same buffer growing over several simulated chunks, as the real
    // stream consumer accumulates it.
    expect(computeVisibleText('Hello <thin')).toBe('Hello ')
    expect(computeVisibleText('Hello <thinking>')).toBe('Hello ')
    expect(computeVisibleText('Hello <thinking>secret')).toBe('Hello ')
    expect(computeVisibleText('Hello <thinking>secret</thi')).toBe('Hello ')
    expect(computeVisibleText('Hello <thinking>secret</thinking> world')).toBe(
      'Hello  world',
    )
  })
})

describe('extractDeltaText', () => {
  it('extracts text from a contentBlockDelta event', () => {
    const event = { event: { contentBlockDelta: { delta: { text: 'hi' }, contentBlockIndex: 0 } } }
    expect(extractDeltaText(event)).toBe('hi')
  })

  it('returns null for unrelated event shapes', () => {
    expect(extractDeltaText({ event: { messageStart: { role: 'assistant' } } })).toBeNull()
    expect(extractDeltaText({ init_event_loop: true })).toBeNull()
    expect(extractDeltaText('not an object')).toBeNull()
    expect(extractDeltaText(null)).toBeNull()
  })
})

describe('splitSseFrames', () => {
  it('splits complete frames and keeps a trailing partial frame as remainder', () => {
    const [frames, remainder] = splitSseFrames('data: a\n\ndata: b\n\ndata: c')
    expect(frames).toEqual(['data: a', 'data: b'])
    expect(remainder).toBe('data: c')
  })
})

describe('parseSseFrame', () => {
  it('parses a valid data frame carrying a text delta', () => {
    const frame = 'data: {"event":{"contentBlockDelta":{"delta":{"text":"hi"},"contentBlockIndex":0}}}'
    expect(parseSseFrame(frame)).toBe('hi')
  })

  it('returns null for non-data frames', () => {
    expect(parseSseFrame('not-a-data-frame')).toBeNull()
  })

  it('returns null for malformed JSON', () => {
    expect(parseSseFrame('data: {not json')).toBeNull()
  })
})

describe('createLiveChatStream', () => {
  function sseResponse(chunks: string[]): Response {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
        controller.close()
      },
    })
    return new Response(stream, { status: 200 })
  }

  async function collect(stream: ReadableStream<string>): Promise<string> {
    const reader = stream.getReader()
    let result = ''
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      result += value
    }
    return result
  }

  it('streams visible text and strips a thinking block split across chunks', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      sseResponse([
        'data: {"init_event_loop":true}\n\n',
        'data: {"event":{"contentBlockDelta":{"delta":{"text":"<thin"},"contentBlockIndex":0}}}\n\n',
        'data: {"event":{"contentBlockDelta":{"delta":{"text":"king>secret</thinking>"},"contentBlockIndex":0}}}\n\n',
        'data: {"event":{"contentBlockDelta":{"delta":{"text":"Real answer"},"contentBlockIndex":0}}}\n\n',
        'data: {"event":{"messageStop":{"stopReason":"end_turn"}}}\n\n',
      ]),
    )

    const stream = createLiveChatStream('hi', 'session-1', {
      functionUrl: 'https://example.invalid/',
      fetchImpl,
    })

    expect(await collect(stream)).toBe('Real answer')
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://example.invalid/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ message: 'hi', sessionId: 'session-1' }),
      }),
    )
  })

  it('errors the stream on a non-OK response', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 500 }))
    const stream = createLiveChatStream('hi', 'session-1', {
      functionUrl: 'https://example.invalid/',
      fetchImpl,
    })
    await expect(collect(stream)).rejects.toThrow()
  })
})
