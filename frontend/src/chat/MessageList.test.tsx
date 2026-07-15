import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MessageList } from './MessageList'
import type { ChatMessage } from './types'

function makeMessages(count: number): ChatMessage[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `m-${i}`,
    role: i % 2 === 0 ? 'user' : 'assistant',
    text: `message ${i}`,
  }))
}

/**
 * jsdom never computes real layout (scrollHeight/clientHeight are always 0),
 * so scroll geometry has to be stubbed by hand. Records every scrollTop
 * assignment so tests can assert whether auto-scroll fired.
 */
function stubScrollGeometry(
  container: HTMLElement,
  { scrollHeight, clientHeight }: { scrollHeight: number; clientHeight: number },
) {
  let scrollTop = 0
  const scrollTopSets: number[] = []
  Object.defineProperty(container, 'scrollHeight', { configurable: true, value: scrollHeight })
  Object.defineProperty(container, 'clientHeight', { configurable: true, value: clientHeight })
  Object.defineProperty(container, 'scrollTop', {
    configurable: true,
    get: () => scrollTop,
    set: (value: number) => {
      scrollTop = value
      scrollTopSets.push(value)
    },
  })
  return { scrollTopSets, setScrollTop: (value: number) => (scrollTop = value) }
}

function getContainer() {
  return screen.getByRole('list', { name: 'Conversation' })
}

describe('MessageList auto-scroll', () => {
  it('scrolls to the bottom when a new message arrives while already pinned', () => {
    const { rerender } = render(<MessageList messages={makeMessages(2)} />)
    const container = getContainer()
    const { scrollTopSets } = stubScrollGeometry(container, { scrollHeight: 1000, clientHeight: 500 })

    rerender(<MessageList messages={makeMessages(3)} />)

    expect(scrollTopSets).toContain(1000)
  })

  it('suspends auto-scroll once the user scrolls up, and does not yank the view back on a content update', () => {
    const { rerender } = render(<MessageList messages={makeMessages(3)} />)
    const container = getContainer()
    const { scrollTopSets, setScrollTop } = stubScrollGeometry(container, {
      scrollHeight: 1000,
      clientHeight: 500,
    })

    // User scrolls up, away from the bottom.
    setScrollTop(100)
    fireEvent.scroll(container)

    // Same message count, just streamed text changing -- must not force the
    // view back down while the user is reading earlier history.
    const updated = makeMessages(3)
    updated[2] = { ...updated[2], text: 'message 2 updated' }
    rerender(<MessageList messages={updated} />)

    expect(scrollTopSets).not.toContain(1000)
  })

  it('resumes auto-scroll when a new message is sent, even after the user had scrolled up', () => {
    const { rerender } = render(<MessageList messages={makeMessages(3)} />)
    const container = getContainer()
    const { scrollTopSets, setScrollTop } = stubScrollGeometry(container, {
      scrollHeight: 1000,
      clientHeight: 500,
    })

    setScrollTop(100)
    fireEvent.scroll(container)

    rerender(<MessageList messages={makeMessages(4)} />)

    expect(scrollTopSets).toContain(1000)
  })
})
