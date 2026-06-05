import { useSources } from '../api/hooks'

export function SourceList() {
  const { data: sources = [] } = useSources()

  return (
    <section className="center-panel" aria-label="Recent Sources">
      <div className="panel-header">
        <h2>Recent Sources</h2>
        <span className="count-pill">{sources.length}</span>
      </div>
      {sources.length > 0 ? (
        <div className="stack-list">
          {sources.map((source) => (
            <article className="list-row" key={source.id}>
              <strong>{source.title}</strong>
              <p>{source.status}</p>
            </article>
          ))}
        </div>
      ) : (
        <p>No sources yet.</p>
      )}
    </section>
  )
}
