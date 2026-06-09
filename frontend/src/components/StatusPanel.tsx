import { useRetrySource, useStatusSummary } from '../api/hooks'

export function StatusPanel() {
  const { data: status } = useStatusSummary()
  const retrySource = useRetrySource()

  if (!status) {
    return (
      <section className="center-panel full-span" aria-label="系统状态">
        <h2>系统状态</h2>
        <p>正在读取状态。</p>
      </section>
    )
  }

  return (
    <section className="center-panel full-span" aria-label="系统状态">
      <div className="panel-header">
        <div>
          <p className="eyebrow">运行状态</p>
          <h2>系统状态</h2>
        </div>
        <span className="count-pill">{status.suggested_actions.length}</span>
      </div>

      <div className="status-grid">
        <article className="status-section">
          <strong>模型运行</strong>
          <p>来源：{status.runtime.runtime_source}</p>
          <p>模型：{status.runtime.llm_model ?? '未配置'}</p>
          {status.runtime.active_profile_name ? <p>当前配置：{status.runtime.active_profile_name}</p> : null}
          {status.runtime.configuration_hint ? <p>{status.runtime.configuration_hint}</p> : null}
        </article>

        <article className="status-section">
          <strong>资料索引</strong>
          <p>资料总数：{status.source_counts.total}</p>
          <p>已索引：{status.source_counts.indexed}</p>
          <p>索引失败：{status.source_counts.failed}</p>
          <p>标签建议：{status.pending_tag_suggestion_count}</p>
        </article>
      </div>

      {status.suggested_actions.length > 0 ? (
        <div className="stack-list">
          <strong>建议动作</strong>
          {status.suggested_actions.map((action) => (
            <p key={action.label}>{action.label}</p>
          ))}
        </div>
      ) : null}

      {status.failed_sources.length > 0 ? (
        <div className="stack-list results-list">
          {status.failed_sources.map((source) => (
            <article className="list-row" key={source.id}>
              <strong>{source.title}</strong>
              {source.error_message ? <p>{source.error_message}</p> : null}
              <div className="memory-actions">
                <button disabled={retrySource.isPending} onClick={() => retrySource.mutate(source.id)} type="button">
                  重试资料
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p>没有失败资料。</p>
      )}
    </section>
  )
}
