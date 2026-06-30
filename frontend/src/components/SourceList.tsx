import { useState } from 'react'

import { useDeleteSource, useIndexSource, useRefreshSource, useRetrySource, useSourceDetail, useSources } from '../api/hooks'
import type { SourceDetailRead } from '../api/types'
import { formatKnowledgePipelineStatus, formatSourceStatus } from '../i18n'
import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'
import { OrganizationControls } from './OrganizationControls'

function formatBytes(value: number) {
  if (value < 1024) return `${value} bytes`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatParseStatus(value: string) {
  if (value === 'pending') return '待解析'
  return formatKnowledgePipelineStatus(value)
}

function formatGraphStatus(value: string) {
  if (value === 'pending') return '待同步'
  return formatKnowledgePipelineStatus(value)
}

function canRefreshSource(source: SourceDetailRead) {
  return source.source_type === 'link' || source.source_type === 'bookmark' || source.source_type === 'web_crawl'
}

export function SourceList() {
  const { activeKnowledgeBase, activeKnowledgeBaseId } = useKnowledgeBaseContext()
  const { data: sources = [] } = useSources(activeKnowledgeBaseId)
  const indexSource = useIndexSource()
  const retrySource = useRetrySource()
  const refreshSource = useRefreshSource()
  const deleteSource = useDeleteSource()
  const [selectedSourceId, setSelectedSourceId] = useState<number>()
  const { data: selectedSource } = useSourceDetail(selectedSourceId)
  const isBusy = indexSource.isPending || retrySource.isPending || refreshSource.isPending || deleteSource.isPending

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
                  <button disabled={isBusy} onClick={() => retrySource.mutate(source.id)} type="button">
                    重试资料
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
              <div className="status-row">
                <span className={`status-chip status-${selectedSource.embedding_status}`}>
                  Embedding：{formatKnowledgePipelineStatus(selectedSource.embedding_status)}
                </span>
                <span className={`status-chip status-${selectedSource.index_status}`}>
                  ES 索引：{formatKnowledgePipelineStatus(selectedSource.index_status)}
                </span>
                <span className={`status-chip status-${selectedSource.graph_status}`}>
                  Graph：{formatGraphStatus(selectedSource.graph_status)}
                </span>
              </div>
              {selectedSource.url || selectedSource.filename ? (
                <p>原始位置：{selectedSource.url ?? selectedSource.filename}</p>
              ) : null}
              {selectedSource.assets.length > 0 ? (
                <div className="asset-list">
                  {selectedSource.assets.map((asset) => (
                    <div className="asset-row" key={asset.id}>
                      <p>文件 asset：{asset.filename}</p>
                      <p className="helper-text">
                        {(asset.mime_type ?? 'unknown') + ' · ' + formatBytes(asset.byte_size)}
                      </p>
                      <div className="status-row">
                        <span className={`status-chip status-${asset.parse_status}`}>
                          Parse：{formatParseStatus(asset.parse_status)}
                        </span>
                        <span className={`status-chip status-${asset.embedding_status}`}>
                          Embedding：{formatKnowledgePipelineStatus(asset.embedding_status)}
                        </span>
                        <span className={`status-chip status-${asset.index_status}`}>
                          ES 索引：{formatKnowledgePipelineStatus(asset.index_status)}
                        </span>
                        <span className={`status-chip status-${asset.graph_status}`}>
                          Graph：{formatGraphStatus(asset.graph_status)}
                        </span>
                      </div>
                      {asset.parse_error ? <p>Parse 错误：{asset.parse_error}</p> : null}
                      {asset.index_error ? <p>Index 错误：{asset.index_error}</p> : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {selectedSource.indexing_runs[0] ? (
                <p className="helper-text">
                  最近索引：{formatKnowledgePipelineStatus(selectedSource.indexing_runs[0].status)} ·{' '}
                  {selectedSource.indexing_runs[0].chunks_embedded}/{selectedSource.indexing_runs[0].chunks_total} chunks
                </p>
              ) : null}
              {selectedSource.error_message ? <p>解析错误：{selectedSource.error_message}</p> : null}
              <OrganizationControls targetType="source" targetId={selectedSource.id} label="资料" tags={selectedSource.tags} />
              <div className="memory-actions">
                {selectedSource.can_retry ? (
                  <button disabled={isBusy} onClick={() => retrySource.mutate(selectedSource.id)} type="button">
                    重试资料
                  </button>
                ) : null}
                {canRefreshSource(selectedSource) ? (
                  <button disabled={isBusy} onClick={() => refreshSource.mutate(selectedSource.id)} type="button">
                    刷新网页资料
                  </button>
                ) : null}
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
