import { ChangeEvent, FormEvent, useRef, useState } from 'react'

import {
  useAskLumen,
  useAskLumenStream,
  useCaptureLink,
  useCreateSource,
  useCrawlWeb,
  useImportBookmarks,
  useUploadSources,
} from '../api/hooks'
import type { BulkUploadResult, ChatResponse } from '../api/types'

type CapturePanelProps = {
  onResponse?: (response: ChatResponse) => void
  onStreamChunk?: (text: string) => void
  onStreamStart?: () => void
}

type CaptureMode = 'note' | 'file' | 'link' | 'bookmarks'

export function CapturePanel({ onResponse, onStreamChunk, onStreamStart }: CapturePanelProps) {
  const [mode, setMode] = useState<CaptureMode>('note')
  const [draft, setDraft] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadResult, setUploadResult] = useState<BulkUploadResult | null>(null)
  const [link, setLink] = useState('')
  const [deepCrawl, setDeepCrawl] = useState(false)
  const [crawlDepth, setCrawlDepth] = useState(1)
  const [crawlMaxPages, setCrawlMaxPages] = useState(10)
  const [bookmarkHtml, setBookmarkHtml] = useState('')
  const [bookmarkResult, setBookmarkResult] = useState<BulkUploadResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const askLumen = useAskLumen()
  const askLumenStream = useAskLumenStream()
  const createSource = useCreateSource()
  const uploadSources = useUploadSources()
  const captureLink = useCaptureLink()
  const crawlWeb = useCrawlWeb()
  const importBookmarks = useImportBookmarks()

  const handleAsk = (event: FormEvent) => {
    event.preventDefault()
    const message = draft.trim()
    if (mode === 'note' && message) {
      onStreamStart?.()
      askLumenStream.mutate(
        { message, onChunk: (text) => onStreamChunk?.(text) },
        {
          onError: () => {
            onStreamStart?.()
            askLumen.mutate(message, { onSuccess: (response) => onResponse?.(response) })
          },
          onSuccess: (response) => onResponse?.(response),
        },
      )
    }
  }

  const handleAddSource = () => {
    const content = draft.trim()
    if (mode === 'note' && content) {
      createSource.mutate({ title: content.slice(0, 72), source_type: 'note', content })
    }
  }

  const resetSelectedFiles = () => {
    setSelectedFiles([])
    setUploadResult(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleFilesSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (files && files.length > 0) {
      setSelectedFiles(Array.from(files))
      setUploadResult(null)
    }
  }

  const handleUpload = () => {
    if (selectedFiles.length === 0) {
      fileInputRef.current?.click()
      return
    }
    uploadSources.mutate(selectedFiles, {
      onSuccess: (result) => {
        setUploadResult(result)
        setSelectedFiles([])
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      },
    })
  }

  const handleCaptureLink = () => {
    const url = link.trim()
    if (!url) return
    if (deepCrawl) {
      crawlWeb.mutate({
        url,
        max_depth: crawlDepth,
        max_pages: crawlMaxPages,
        same_domain_only: true,
      })
    } else {
      captureLink.mutate(url)
    }
  }

  const handleImportBookmarks = () => {
    const htmlContent = bookmarkHtml.trim()
    if (!htmlContent) return
    importBookmarks.mutate(htmlContent, {
      onSuccess: (result) => {
        setBookmarkResult(result)
        setBookmarkHtml('')
      },
    })
  }

  const isBusy =
    askLumen.isPending ||
    askLumenStream.isPending ||
    createSource.isPending ||
    uploadSources.isPending ||
    captureLink.isPending ||
    crawlWeb.isPending ||
    importBookmarks.isPending
  const canUseDraft = mode === 'note' && Boolean(draft.trim())

  return (
    <section className="center-panel" aria-label="询问或记录">
      <div className="panel-header">
        <div>
          <p className="eyebrow">主工作区</p>
          <h2>询问或记录</h2>
        </div>
        <span className="mode-pill">{isBusy ? '处理中' : '就绪'}</span>
      </div>
      <div className="segmented-control" aria-label="资料接入模式">
        <button className={mode === 'note' ? 'active' : ''} onClick={() => setMode('note')} type="button">
          笔记
        </button>
        <button className={mode === 'file' ? 'active' : ''} onClick={() => setMode('file')} type="button">
          文件
        </button>
        <button className={mode === 'link' ? 'active' : ''} onClick={() => setMode('link')} type="button">
          链接
        </button>
        <button className={mode === 'bookmarks' ? 'active' : ''} onClick={() => setMode('bookmarks')} type="button">
          书签
        </button>
      </div>

      {mode === 'note' ? (
        <form onSubmit={handleAsk}>
          <label className="field-label" htmlFor="ask-lumen">
            输入问题、写一条笔记，或粘贴一段资料
          </label>
          <textarea
            id="ask-lumen"
            aria-label="询问 Lumen"
            onChange={(event) => setDraft(event.target.value)}
            placeholder="例如：2026年6月1日做了什么工作？"
            value={draft}
          />
          <div className="action-row">
            <button disabled={isBusy || !canUseDraft} type="submit">
              询问 Lumen
            </button>
            <button disabled={isBusy || !canUseDraft} onClick={handleAddSource} type="button" className="secondary">
              添加资料
            </button>
          </div>
        </form>
      ) : null}

      {mode === 'file' ? (
        <div className="form-stack">
          <label className="field-label" htmlFor="source-file">
            选择资料文件
          </label>
          <input
            accept=".txt,.md,.pdf,.docx,.epub,.png,.jpg,.jpeg,.gif,.webp"
            id="source-file"
            multiple
            onChange={handleFilesSelected}
            ref={fileInputRef}
            type="file"
          />
          <p className="helper-text">
            {selectedFiles.length > 0
              ? `已选择 ${selectedFiles.length} 个文件`
              : '支持 TXT、Markdown、PDF、DOCX、EPUB、PNG、JPG、JPEG、GIF、WEBP。选择文件后点击上传。'}
          </p>
          {uploadResult ? (
            <p className="helper-text">
              上传完成：成功 {uploadResult.succeeded}，失败 {uploadResult.failed}
            </p>
          ) : null}
          <div className="action-row">
            <button disabled={isBusy} onClick={handleUpload} type="button">
              {selectedFiles.length > 0 ? '上传文件' : '选择文件'}
            </button>
            {selectedFiles.length > 0 || uploadResult ? (
              <button disabled={isBusy} onClick={resetSelectedFiles} type="button" className="secondary">
                清除
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {mode === 'link' ? (
        <div className="form-stack">
          <label className="field-label" htmlFor="source-link">
            网页链接
          </label>
          <input
            id="source-link"
            onChange={(event) => setLink(event.target.value)}
            placeholder="https://example.com/article"
            type="url"
            value={link}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={deepCrawl}
              onChange={(event) => setDeepCrawl(event.target.checked)}
            />
            <span>深度抓取（递归抓取同域页面）</span>
          </label>
          {deepCrawl ? (
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>深度</span>
                <input
                  type="number"
                  min={1}
                  max={3}
                  value={crawlDepth}
                  onChange={(event) => setCrawlDepth(Math.min(3, Math.max(1, Number(event.target.value))))}
                  style={{ width: '4rem' }}
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>最大页数</span>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={crawlMaxPages}
                  onChange={(event) => setCrawlMaxPages(Math.min(50, Math.max(1, Number(event.target.value))))}
                  style={{ width: '4rem' }}
                />
              </label>
            </div>
          ) : null}
          <div className="action-row">
            <button disabled={isBusy || !link.trim()} onClick={handleCaptureLink} type="button">
              {deepCrawl ? '深度抓取' : '添加链接'}
            </button>
          </div>
        </div>
      ) : null}

      {mode === 'bookmarks' ? (
        <div className="form-stack">
          <label className="field-label" htmlFor="bookmark-html">
            粘贴 Netscape HTML 书签内容
          </label>
          <textarea
            id="bookmark-html"
            aria-label="书签 HTML 内容"
            onChange={(event) => setBookmarkHtml(event.target.value)}
            placeholder="粘贴从浏览器导出的书签 HTML 内容..."
            value={bookmarkHtml}
            rows={8}
          />
          {bookmarkResult ? (
            <p className="helper-text">
              导入完成：共 {bookmarkResult.total} 个，成功 {bookmarkResult.succeeded} 个
            </p>
          ) : null}
          <div className="action-row">
            <button disabled={isBusy || !bookmarkHtml.trim()} onClick={handleImportBookmarks} type="button">
              导入书签
            </button>
            {bookmarkResult ? (
              <button
                disabled={isBusy}
                onClick={() => setBookmarkResult(null)}
                type="button"
                className="secondary"
              >
                清除结果
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  )
}
