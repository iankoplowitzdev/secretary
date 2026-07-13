import type { ChatMessage } from './types'

interface MessageListProps {
  messages: ChatMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <ul className="message-list" aria-live="polite" aria-label="Conversation">
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
            {message.text}
            {message.streaming ? (
              <span className="message-cursor" aria-hidden="true">
                ▍
              </span>
            ) : null}
          </p>
        </li>
      ))}
    </ul>
  )
}
