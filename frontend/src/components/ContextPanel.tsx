import type { ChatResponse } from '../api/types'

type ContextPanelProps = {
  response?: ChatResponse
}

export function ContextPanel({ response }: ContextPanelProps) {
  return (
    <section className="side-panel">
      <h2>Context Now</h2>
      {response ? (
        <div className="stack-list">
          <p>
            Confidence: <strong>{response.confidence}</strong>
          </p>
          {response.citations.map((citation) => (
            <article className="list-row" key={`${citation.source_id}-${citation.chunk_id}`}>
              <strong>{citation.source_title}</strong>
              <p>{citation.quote}</p>
            </article>
          ))}
        </div>
      ) : (
        <p>Sources and recalled memories will appear here.</p>
      )}
    </section>
  )
}
