import { describe, expect, it } from 'vitest'
import { createMockChatStream } from './mockChatStream'

async function collectChunks(stream: ReadableStream<string>): Promise<string[]> {
  const reader = stream.getReader()
  const chunks: string[] = []
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    if (value) chunks.push(value)
  }
  return chunks
}

describe('createMockChatStream', () => {
  it('emits multiple chunks that concatenate into non-empty text', async () => {
    const stream = createMockChatStream('hello', 'session-1', {
      chunkDelayMs: 1,
    })
    const chunks = await collectChunks(stream)
    expect(chunks.length).toBeGreaterThan(1)
    expect(chunks.join('')).toEqual(expect.stringMatching(/\S/))
  })

  it('is a real ReadableStream', () => {
    const stream = createMockChatStream('hello', 'session-1', {
      chunkDelayMs: 1,
    })
    expect(stream).toBeInstanceOf(ReadableStream)
  })
})
