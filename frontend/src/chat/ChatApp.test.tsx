import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatApp } from './ChatApp'
import * as chatClient from '../api/chatClient'
import { __resetSessionIdForTests } from '../lib/session'

/**
 * Builds a controllable ReadableStream<string> plus functions to push chunks
 * and finish/close it on demand, so tests can assert on intermediate render
 * states rather than just the final one.
 */
function createControllableStream() {
  let controllerRef: ReadableStreamDefaultController<string>
  const stream = new ReadableStream<string>({
    start(controller) {
      controllerRef = controller
    },
  })
  return {
    stream,
    push: (chunk: string) => controllerRef.enqueue(chunk),
    finish: () => controllerRef.close(),
  }
}

describe('ChatApp', () => {
  beforeEach(() => {
    __resetSessionIdForTests()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sends a message and shows it in the message list', async () => {
    const user = userEvent.setup()
    const controllable = createControllableStream()
    vi.spyOn(chatClient, 'sendChatMessage').mockReturnValue(controllable.stream)

    render(<ChatApp />)

    const input = screen.getByLabelText(/message/i)
    await user.type(input, 'Hello there')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(screen.getByText('Hello there')).toBeInTheDocument()

    controllable.finish()
  })

  it('renders assistant response incrementally as stream chunks arrive', async () => {
    const user = userEvent.setup()
    const controllable = createControllableStream()
    vi.spyOn(chatClient, 'sendChatMessage').mockReturnValue(controllable.stream)

    render(<ChatApp />)

    await user.type(screen.getByLabelText(/message/i), 'Tell me something')
    await user.click(screen.getByRole('button', { name: /send/i }))

    const assistantText = () =>
      screen
        .getAllByText('Assistant', { selector: '.message-author' })[0]
        .closest('li')!
        .querySelector('.message-text')!.textContent ?? ''

    // Nothing streamed yet (only the blinking cursor is present).
    expect(assistantText().replace('▍', '').trim()).toBe('')

    controllable.push('Hello')
    await waitFor(() => {
      expect(assistantText()).toContain('Hello')
    })
    // Assert this is a genuine intermediate state, not the final text yet.
    expect(assistantText()).not.toContain('Hello world, done')

    controllable.push(' world')
    await waitFor(() => {
      expect(assistantText()).toContain('Hello world')
    })
    expect(assistantText()).not.toContain('Hello world, done')

    controllable.push(', done')
    controllable.finish()
    await waitFor(() => {
      expect(assistantText()).toContain('Hello world, done')
    })
  })

  it('uses the same session id across multiple sent messages in one mounted session', async () => {
    const user = userEvent.setup()
    const seenSessionIds: string[] = []

    vi.spyOn(chatClient, 'sendChatMessage').mockImplementation(({ sessionId }) => {
      seenSessionIds.push(sessionId)
      const c = createControllableStream()
      c.finish()
      return c.stream
    })

    render(<ChatApp />)

    const input = screen.getByLabelText(/message/i)

    await user.type(input, 'First message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(seenSessionIds).toHaveLength(1))

    await user.type(input, 'Second message')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(seenSessionIds).toHaveLength(2))

    expect(seenSessionIds[0]).toBe(seenSessionIds[1])
    expect(seenSessionIds[0]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    )
  })
})
