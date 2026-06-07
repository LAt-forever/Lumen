import type { ChatResponse } from '../api/types'
import { formatConfidence } from '../i18n'

type ContextPanelProps = {
  response?: ChatResponse
}

export function ContextPanel({ response }: ContextPanelProps) {
  return (
    <section className="side-panel">
      <h2>当前上下文</h2>
      {response ? (
        <div className="stack-list">
          <p>
            置信度：<strong>{formatConfidence(response.confidence)}</strong>
          </p>
          {response.citations.map((citation) => (
            <article className="list-row" key={`${citation.source_id}-${citation.chunk_id}`}>
              <strong>{citation.source_title}</strong>
              <p>{citation.quote}</p>
            </article>
          ))}
        </div>
      ) : (
        <p>资料来源、引用片段和召回的记忆会显示在这里。</p>
      )}
    </section>
  )
}
