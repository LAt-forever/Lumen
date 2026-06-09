import { FormEvent, useState } from 'react'

import { useFavoriteTarget, useGlobalSearch, useTags, useUnfavoriteTarget } from '../api/hooks'
import type { GlobalSearchResultRead, TargetType } from '../api/types'

const resultTypeLabels: Record<GlobalSearchResultRead['result_type'], string> = {
  source_chunk: '资料片段',
  source: '资料',
  memory: '记忆',
  message: '对话',
}

export function SearchPanel() {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [tagFilter, setTagFilter] = useState('')
  const [favoriteOnly, setFavoriteOnly] = useState(false)
  const { data: tags = [] } = useTags()
  const { data: results = [] } = useGlobalSearch({ query, type: typeFilter, tag: tagFilter, favorite: favoriteOnly })
  const favoriteTarget = useFavoriteTarget()
  const unfavoriteTarget = useUnfavoriteTarget()

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    setQuery(draft.trim())
  }

  const toggleFavorite = (result: GlobalSearchResultRead) => {
    if (result.result_type === 'source_chunk') return
    const targetType = result.result_type as TargetType
    if (result.is_favorite) {
      unfavoriteTarget.mutate({ target_type: targetType, target_id: result.target_id })
      return
    }
    favoriteTarget.mutate({ target_type: targetType, target_id: result.target_id })
  }

  return (
    <section className="center-panel full-span" aria-label="资料搜索面板">
      <div className="panel-header">
        <div>
          <p className="eyebrow">全局检索</p>
          <h2>全局搜索</h2>
        </div>
        <span className="count-pill">{results.length}</span>
      </div>
      <form onSubmit={handleSearch}>
        <label className="field-label" htmlFor="global-search">
          全局搜索
        </label>
        <input
          id="global-search"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="输入关键词、日期或项目名"
          value={draft}
        />
        <div className="segmented-control" aria-label="结果类型">
          {[
            ['all', '全部'],
            ['source', '资料'],
            ['memory', '记忆'],
            ['message', '对话'],
          ].map(([value, label]) => (
            <button
              className={typeFilter === value ? 'active' : ''}
              key={value}
              onClick={() => setTypeFilter(value)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="search-filter-row">
          <label className="field-label" htmlFor="tag-filter">
            标签
          </label>
          <select id="tag-filter" onChange={(event) => setTagFilter(event.target.value)} value={tagFilter}>
            <option value="">全部标签</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.name}>
                {tag.name}
              </option>
            ))}
          </select>
          <label className="checkbox-row">
            <input checked={favoriteOnly} onChange={(event) => setFavoriteOnly(event.target.checked)} type="checkbox" />
            <span>只看收藏</span>
          </label>
        </div>
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
            <article className="list-row" key={`${result.result_type}-${result.target_id}`}>
              <div className="result-title-row">
                <strong>{result.title}</strong>
                <span className="mode-pill">{resultTypeLabels[result.result_type]}</span>
              </div>
              <p>{result.snippet}</p>
              {result.tags.length > 0 ? (
                <div className="tag-row">
                  {result.tags.map((tag) => (
                    <span className="tag-chip" key={tag.id}>
                      {tag.name}
                    </span>
                  ))}
                </div>
              ) : null}
              {result.match_reason ? <p>{result.match_reason}</p> : null}
              <p>相关度：{result.score.toFixed(2)}</p>
              {result.result_type !== 'source_chunk' ? (
                <div className="memory-actions">
                  <button onClick={() => toggleFavorite(result)} type="button">
                    {result.is_favorite ? '取消收藏' : '收藏'}
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  )
}
