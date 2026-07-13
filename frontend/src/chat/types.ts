export type MessageRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: MessageRole
  text: string
  /** True while an assistant message is still receiving streamed chunks. */
  streaming?: boolean
}
