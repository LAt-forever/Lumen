import { FormEvent, useState } from 'react'

import { useSearch } from '../api/hooks'

export function SearchPanel() {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const { data: results = [] } = useSearch(query)

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    setQuery(draft.trim())
  }

  return (
    <section className="center-panel full-span" aria-label="资料搜索面板">
      <div className="panel-header">
        <div>
          <p className="eyebrow">全局检索</p>
          <h2>搜索资料</h2>
        </div>
        <span className="count-pill">{results.length}</span>
      </div>
      <form onSubmit={handleSearch}>
        <label className="field-label" htmlFor="knowledge-search">
          搜索资料
        </label>
        <input
          id="knowledge-search"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="输入关键词、日期或项目名"
          value={draft}
        />
        <div className="action-row">
          <button disabled={!draft.trim()} type="submit">
            执行搜索
          </button>
        </div>
      </form>
      {query && results.length === 0 ? <p>没有找到匹配资料。</p> : null}
      {results.length > 0 ? (
        <div className="stack-list results-list">
          {results.map((result) => (
            <article className="list-row" key={result.id}>
              <strong>{result.source_title}</strong>
              <p>{result.text}</p>
              <p>相关度：{result.score.toFixed(2)}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  )
}
