import { useState } from 'react'

import { useImageSources, useRetrySource, useSourceDetail } from '../api/hooks'
import type { SourceAssetRead, SourceDetailRead } from '../api/types'
import { formatKnowledgePipelineStatus, formatSourceStatus } from '../i18n'
import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'
import { OrganizationControls } from './OrganizationControls'

function formatBytes(value: number) {
  if (value < 1024) return `${value} bytes`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function parseStatusLabel(value: string) {
  if (value === 'pending') return '待解析'
  return formatKnowledgePipelineStatus(value)
}

function graphStatusLabel(value: string) {
  if (value === 'pending') return '待同步'
  return formatKnowledgePipelineStatus(value)
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <span className={`status-chip status-${value}`}>
      {label}：{formatKnowledgePipelineStatus(value)}
    </span>
  )
}

function AssetMetadata({ asset }: { asset: SourceAssetRead }) {
  return (
    <p className="helper-text">
      {(asset.mime_type ?? 'unknown') + ' · ' + formatBytes(asset.byte_size)}
    </p>
  )
}

function ImageDetail({ detail }: { detail: SourceDetailRead }) {
  const retrySource = useRetrySource()
  const asset = detail.assets[0]
  const latestRun = detail.indexing_runs[0]
  const isBusy = retrySource.isPending

  return (
    <article className="list-row image-detail">
      <strong>图片详情</strong>
      <p>{detail.title}</p>
      <p>状态：{formatSourceStatus(detail.status)}</p>
      <p>索引片段：{detail.chunk_count}</p>
      {asset ? (
        <>
          <p>文件 asset：{asset.filename}</p>
          <AssetMetadata asset={asset} />
          <div className="status-row">
            <span className={`status-chip status-${asset.parse_status}`}>Parse：{parseStatusLabel(asset.parse_status)}</span>
            <StatusLine label="Embedding" value={detail.embedding_status} />
            <StatusLine label="ES 索引" value={detail.index_status} />
            <span className={`status-chip status-${detail.graph_status}`}>Graph：{graphStatusLabel(detail.graph_status)}</span>
          </div>
          {asset.parse_error ? <p>Parse 错误：{asset.parse_error}</p> : null}
          {asset.index_error ? <p>Index 错误：{asset.index_error}</p> : null}
        </>
      ) : null}
      {latestRun ? (
        <p className="helper-text">
          最近索引：{formatKnowledgePipelineStatus(latestRun.status)} · {latestRun.chunks_embedded}/{latestRun.chunks_total} chunks
        </p>
      ) : null}
      <OrganizationControls targetType="source" targetId={detail.id} label="图片" tags={detail.tags} />
      {detail.can_retry ? (
        <div className="memory-actions">
          <button disabled={isBusy} onClick={() => retrySource.mutate(detail.id)} type="button">
            重试图片索引
          </button>
        </div>
      ) : null}
    </article>
  )
}

export function ImageLibraryPanel() {
  const { activeKnowledgeBase, activeKnowledgeBaseId } = useKnowledgeBaseContext()
  const { data: images = [] } = useImageSources(activeKnowledgeBaseId)
  const [selectedSourceId, setSelectedSourceId] = useState<number>()
  const { data: selectedSource } = useSourceDetail(selectedSourceId)

  return (
    <section className="center-panel" aria-label="图片库">
      <div className="panel-header">
        <div>
          <h2>图片资产</h2>
          {activeKnowledgeBase ? <p className="helper-text">{activeKnowledgeBase.name}</p> : null}
        </div>
        <span className="count-pill">{images.length}</span>
      </div>

      {images.length > 0 ? (
        <div className="stack-list">
          {images.map((image) => (
            <article className="list-row image-row" key={image.id}>
              <strong>{image.title}</strong>
              <AssetMetadata asset={image.asset} />
              <div className="status-row">
                <span className={`status-chip status-${image.asset.parse_status}`}>
                  OCR / Vision：{parseStatusLabel(image.asset.parse_status)}
                </span>
                <StatusLine label="Embedding" value={image.asset.embedding_status} />
                <StatusLine label="ES 索引" value={image.asset.index_status} />
                <span className={`status-chip status-${image.asset.graph_status}`}>
                  Graph：{graphStatusLabel(image.asset.graph_status)}
                </span>
              </div>
              {image.error_message ? <p>{image.error_message}</p> : null}
              <OrganizationControls targetType="source" targetId={image.id} label="图片" tags={image.tags} />
              <div className="memory-actions">
                <button onClick={() => setSelectedSourceId(image.id)} type="button">
                  查看图片详情
                </button>
              </div>
            </article>
          ))}
          {selectedSource ? <ImageDetail detail={selectedSource} /> : null}
        </div>
      ) : (
        <p>暂无图片。</p>
      )}
    </section>
  )
}
