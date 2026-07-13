import { useCallback, useRef, useState } from 'react'
import { sendChatMessage } from '../api/chatClient'
import { getSessionId } from '../lib/session'
import { MessageInput } from './MessageInput'
import { MessageList } from './MessageList'
import type { ChatMessage } from './types'

let messageCounter = 0
function nextId(prefix: string): string {
  messageCounter += 1
  return `${prefix}-${messageCounter}`
}

export function ChatApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const sessionId = useRef(getSessionId()).current

  const handleSend = useCallback(
    (text: string) => {
      const userMessage: ChatMessage = {
        id: nextId('user'),
        role: 'user',
        text,
      }

      const assistantId = nextId('assistant')
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        text: '',
        streaming: true,
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setIsStreaming(true)

      const stream = sendChatMessage({ message: text, sessionId })
      const reader = stream.getReader()

      const appendChunk = (chunk: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, text: m.text + chunk } : m,
          ),
        )
      }

      const finishStreaming = () => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, streaming: false } : m,
          ),
        )
        setIsStreaming(false)
      }

      const pump = (): void => {
        reader
          .read()
          .then(({ done, value }) => {
            if (done) {
              finishStreaming()
              return
            }
            if (value) appendChunk(value)
            pump()
          })
          .catch(() => {
            finishStreaming()
          })
      }

      pump()
    },
    [sessionId],
  )

  return (
    <div className="chat-app">
      <header className="chat-header">
        <h1>Secretary</h1>
        <p>Ask me about the owner&apos;s work history, skills, or projects.</p>
      </header>
      <MessageList messages={messages} />
      <MessageInput onSend={handleSend} disabled={isStreaming} />
    </div>
  )
}
