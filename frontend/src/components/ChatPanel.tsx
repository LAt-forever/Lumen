import type { ChatResponse } from '../api/types'
import { formatConfidence } from '../i18n'

type ChatPanelProps = {
  response?: ChatResponse
}

export function ChatPanel({ response }: ChatPanelProps) {
  const answerModeLabel = response?.answer_mode === 'llm' ? 'LLM 模式' : '摘录模式'

  return (
    <section className="center-panel" aria-label="对话">
      <h2>对话</h2>
      {response ? (
        <div className="stack-list">
          <p className="answer-text">{response.answer}</p>
          <p>
            置信度：<strong>{formatConfidence(response.confidence)}</strong>
          </p>
          <p>
            回答模式：<strong>{answerModeLabel}</strong>
          </p>
        </div>
      ) : (
        <p>向 Lumen 提问，开始一段对话。</p>
      )}
    </section>
  )
}
