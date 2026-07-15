import { useEffect, useRef, useState } from 'react'
import type { ChatMessage } from './types'

interface MessageListProps {
  messages: ChatMessage[]
}

const BOTTOM_THRESHOLD_PX = 40

export function MessageList({ messages }: MessageListProps) {
  const containerRef = useRef<HTMLUListElement>(null)
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true)
  const previousLengthRef = useRef(messages.length)

  // Deliberately keyed only on `messages`, not `isPinnedToBottom` -- a plain
  // scroll event (handled below) should never itself trigger a re-scroll,
  // only new/updated message content should.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const grew = messages.length > previousLengthRef.current
    previousLengthRef.current = messages.length

    // Sending (or receiving) a new message always resumes auto-scroll, even
    // if the user had scrolled up to read earlier history.
    if (grew) {
      setIsPinnedToBottom(true)
      container.scrollTop = container.scrollHeight
    } else if (isPinnedToBottom) {
      container.scrollTop = container.scrollHeight
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

  const handleScroll = () => {
    const container = containerRef.current
    if (!container) return
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight
    setIsPinnedToBottom(distanceFromBottom <= BOTTOM_THRESHOLD_PX)
  }

  return (
    <ul
      className="message-list"
      aria-live="polite"
      aria-label="Conversation"
      ref={containerRef}
      onScroll={handleScroll}
    >
      {messages.map((message) => (
        <li
          key={message.id}
          className={`message message-${message.role}`}
          data-role={message.role}
          data-streaming={message.streaming ? 'true' : 'false'}
        >
          <span className="message-author">
            {message.role === 'user' ? 'You' : 'Assistant'}
          </span>
          <p className="message-text">
            {message.streaming && message.text === '' ? (
              <span className="message-thinking">Thinking…</span>
            ) : (
              <>
                {message.text}
                {message.streaming ? (
                  <span className="message-cursor" aria-hidden="true">
                    ▍
                  </span>
                ) : null}
              </>
            )}
          </p>
        </li>
      ))}
    </ul>
  )
}
