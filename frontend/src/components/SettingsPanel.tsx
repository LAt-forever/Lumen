import { API_BASE } from '../api/client'

export function SettingsPanel() {
  return (
    <section className="center-panel full-span" aria-label="设置">
      <div className="panel-header">
        <div>
          <p className="eyebrow">本地运行</p>
          <h2>设置</h2>
        </div>
      </div>
      <div className="stack-list">
        <article className="list-row">
          <strong>API 地址</strong>
          <p>{API_BASE}</p>
        </article>
        <article className="list-row">
          <strong>回答模式</strong>
          <p>摘录模式，不需要模型 API key。</p>
        </article>
        <article className="list-row">
          <strong>数据策略</strong>
          <p>默认写入本地 SQLite 数据库。</p>
        </article>
      </div>
    </section>
  )
}
