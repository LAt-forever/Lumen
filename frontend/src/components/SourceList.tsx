import { useState } from 'react'

import { useDeleteSource, useIndexSource, useSourceDetail, useSources } from '../api/hooks'
import { formatSourceStatus } from '../i18n'
import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'
import { OrganizationControls } from './OrganizationControls'

export function SourceList() {
  const { activeKnowledgeBase, activeKnowledgeBaseId } = useKnowledgeBaseContext()
  const { data: sources = [] } = useSources(activeKnowledgeBaseId)
  const indexSource = useIndexSource()
  const deleteSource = useDeleteSource()
  const [selectedSourceId, setSelectedSourceId] = useState<number>()
  const { data: selectedSource } = useSourceDetail(selectedSourceId)
  const isBusy = indexSource.isPending || deleteSource.isPending

  const handleDelete = (sourceId: number) => {
    if (!window.confirm('删除这条资料后，它的片段不会再用于新的搜索和回答。')) {
      return
    }
    deleteSource.mutate(sourceId, { onSuccess: () => setSelectedSourceId(undefined) })
  }

  return (
    <section className="center-panel" aria-label="最近资料">
      <div className="panel-header">
        <div>
          <h2>最近资料</h2>
          {activeKnowledgeBase ? <p className="helper-text">{activeKnowledgeBase.name}</p> : null}
        </div>
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
                  <button disabled={isBusy} onClick={() => indexSource.mutate(source.id)} type="button">
                    重试索引
                  </button>
                </div>
              ) : null}
              <OrganizationControls targetType="source" targetId={source.id} label="资料" />
              <div className="memory-actions">
                <button disabled={isBusy} onClick={() => setSelectedSourceId(source.id)} type="button">
                  查看详情
                </button>
              </div>
            </article>
          ))}
          {selectedSource ? (
            <article className="list-row">
              <strong>资料详情</strong>
              <p>{selectedSource.title}</p>
              <p>状态：{formatSourceStatus(selectedSource.status)}</p>
              <p>索引片段：{selectedSource.chunk_count}</p>
              {selectedSource.url || selectedSource.filename ? (
                <p>原始位置：{selectedSource.url ?? selectedSource.filename}</p>
              ) : null}
              {selectedSource.error_message ? <p>解析错误：{selectedSource.error_message}</p> : null}
              <OrganizationControls targetType="source" targetId={selectedSource.id} label="资料" />
              <div className="memory-actions">
                <button disabled={isBusy} onClick={() => indexSource.mutate(selectedSource.id)} type="button">
                  重试索引
                </button>
                <button disabled={isBusy} onClick={() => handleDelete(selectedSource.id)} type="button" className="secondary">
                  删除资料
                </button>
              </div>
            </article>
          ) : null}
        </div>
      ) : (
        <p>暂无资料。</p>
      )}
    </section>
  )
}
