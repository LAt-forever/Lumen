import type { ChatResponse } from '../api/types'
import { formatConfidence } from '../i18n'

type ContextPanelProps = {
  response?: ChatResponse
}

function retrievalLabel(citation: ChatResponse['citations'][number]) {
  return citation.retrieval_source ?? citation.retrieval_mode ?? null
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
          {response.fallback_reason ? (
            <article className="list-row">
              <strong>回退说明</strong>
              <p>{response.fallback_reason}</p>
            </article>
          ) : null}
          {response.citations.map((citation) => (
            <article className="list-row" key={`${citation.source_id}-${citation.chunk_id}`}>
              <strong>{citation.source_title}</strong>
              <p>{citation.quote}</p>
              {retrievalLabel(citation) ? <p className="helper-text">检索：{retrievalLabel(citation)}</p> : null}
              {citation.match_reason ? <p>{citation.match_reason}</p> : null}
            </article>
          ))}
        </div>
      ) : (
        <p>资料来源、引用片段和召回的记忆会显示在这里。</p>
      )}
    </section>
  )
}
