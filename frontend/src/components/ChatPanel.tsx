import type { ChatResponse } from '../api/types'

type ChatPanelProps = {
  response?: ChatResponse
}

export function ChatPanel({ response }: ChatPanelProps) {
  return (
    <section className="center-panel" aria-label="Conversation">
      <h2>Conversation</h2>
      {response ? (
        <div className="stack-list">
          <p className="answer-text">{response.answer}</p>
          <p>
            Confidence: <strong>{response.confidence}</strong>
          </p>
        </div>
      ) : (
        <p>Ask Lumen a question to start a conversation.</p>
      )}
    </section>
  )
}
