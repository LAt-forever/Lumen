import { useIndexSource, useSources } from '../api/hooks'
import { formatSourceStatus } from '../i18n'

export function SourceList() {
  const { data: sources = [] } = useSources()
  const indexSource = useIndexSource()

  return (
    <section className="center-panel" aria-label="最近资料">
      <div className="panel-header">
        <h2>最近资料</h2>
        <span className="count-pill">{sources.length}</span>
      </div>
      {sources.length > 0 ? (
        <div className="stack-list">
          {sources.map((source) => (
            <article className="list-row" key={source.id}>
              <strong>{source.title}</strong>
              <p>{formatSourceStatus(source.status)}</p>
              {source.error_message ? <p>{source.error_message}</p> : null}
              {source.status === 'failed' ? (
                <div className="memory-actions">
                  <button disabled={indexSource.isPending} onClick={() => indexSource.mutate(source.id)} type="button">
                    重试索引
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p>暂无资料。</p>
      )}
    </section>
  )
}
