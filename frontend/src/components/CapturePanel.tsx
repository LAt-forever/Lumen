import { ChangeEvent, FormEvent, useRef, useState } from 'react'

import {
  useAskLumen,
  useAskLumenStream,
  useCaptureIngestionLink,
  useCreateIngestionNote,
  useCrawlIngestionWeb,
  useImportIngestionBookmarks,
  useUploadIngestionSources,
} from '../api/hooks'
import type { ChatResponse, IngestionBatchRead } from '../api/types'
import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'

type CapturePanelProps = {
  onResponse?: (response: ChatResponse, knowledgeBaseId: number | null, requestId: number) => void
  onStreamChunk?: (text: string, knowledgeBaseId: number | null, requestId: number) => void
  onStreamStart?: (knowledgeBaseId: number | null) => number | null
}

type CaptureMode = 'note' | 'file' | 'link' | 'bookmarks'

export function CapturePanel({ onResponse, onStreamChunk, onStreamStart }: CapturePanelProps) {
  const [mode, setMode] = useState<CaptureMode>('note')
  const [draft, setDraft] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadResult, setUploadResult] = useState<IngestionBatchRead | null>(null)
  const [link, setLink] = useState('')
  const [linkResult, setLinkResult] = useState<IngestionBatchRead | null>(null)
  const [deepCrawl, setDeepCrawl] = useState(false)
  const [crawlDepth, setCrawlDepth] = useState(1)
  const [crawlMaxPages, setCrawlMaxPages] = useState(10)
  const [bookmarkHtml, setBookmarkHtml] = useState('')
  const [bookmarkResult, setBookmarkResult] = useState<IngestionBatchRead | null>(null)
  const [noteResult, setNoteResult] = useState<IngestionBatchRead | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { activeKnowledgeBaseId } = useKnowledgeBaseContext()
  const askLumen = useAskLumen(activeKnowledgeBaseId)
  const askLumenStream = useAskLumenStream(activeKnowledgeBaseId)
  const createSource = useCreateIngestionNote()
  const uploadSources = useUploadIngestionSources()
  const captureLink = useCaptureIngestionLink()
  const crawlWeb = useCrawlIngestionWeb()
  const importBookmarks = useImportIngestionBookmarks()

  const handleAsk = (event: FormEvent) => {
    event.preventDefault()
    const message = draft.trim()
    if (mode === 'note' && message) {
      const requestId = onStreamStart?.(activeKnowledgeBaseId)
      if (requestId === undefined || requestId === null) return
      askLumenStream.mutate(
        { message, onChunk: (text) => onStreamChunk?.(text, activeKnowledgeBaseId, requestId) },
        {
          onError: () => {
            const fallbackRequestId = onStreamStart?.(activeKnowledgeBaseId)
            if (fallbackRequestId === undefined || fallbackRequestId === null) return
            askLumen.mutate(message, {
              onSuccess: (response) => onResponse?.(response, activeKnowledgeBaseId, fallbackRequestId),
            })
          },
          onSuccess: (response) => onResponse?.(response, activeKnowledgeBaseId, requestId),
        },
      )
    }
  }

  const handleAddSource = () => {
    const content = draft.trim()
    if (mode === 'note' && content) {
      createSource.mutate(
        { title: content.slice(0, 72), source_type: 'note', content, knowledge_base_id: activeKnowledgeBaseId },
        {
          onSuccess: (result) => {
            setNoteResult(result)
            setDraft('')
          },
        },
      )
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
    uploadSources.mutate({ files: selectedFiles, knowledge_base_id: activeKnowledgeBaseId }, {
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
    const onSuccess = (result: IngestionBatchRead) => {
      setLinkResult(result)
      setLink('')
    }
    if (deepCrawl) {
      crawlWeb.mutate(
        {
          url,
          max_depth: crawlDepth,
          max_pages: crawlMaxPages,
          same_domain_only: true,
          knowledge_base_id: activeKnowledgeBaseId,
        },
        { onSuccess },
      )
    } else {
      captureLink.mutate({ url, knowledge_base_id: activeKnowledgeBaseId }, { onSuccess })
    }
  }

  const handleImportBookmarks = () => {
    const htmlContent = bookmarkHtml.trim()
    if (!htmlContent) return
    importBookmarks.mutate({ html_content: htmlContent, knowledge_base_id: activeKnowledgeBaseId }, {
      onSuccess: (result) => {
        setBookmarkResult(result)
        setBookmarkHtml('')
      },
    })
  }

  const askBusy = askLumen.isPending || askLumenStream.isPending
  const submitBusy =
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
        <span className="mode-pill">{submitBusy ? '提交中' : askBusy ? '回答中' : '就绪'}</span>
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
          {noteResult ? <p className="helper-text">已加入队列：{noteResult.total} 个任务</p> : null}
          <div className="action-row">
            <button disabled={askBusy || !canUseDraft} type="submit">
              询问 Lumen
            </button>
            <button disabled={submitBusy || !canUseDraft} onClick={handleAddSource} type="button" className="secondary">
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
              已加入队列：{uploadResult.total} 个任务
            </p>
          ) : null}
          <div className="action-row">
            <button disabled={submitBusy} onClick={handleUpload} type="button">
              {selectedFiles.length > 0 ? '上传文件' : '选择文件'}
            </button>
            {selectedFiles.length > 0 || uploadResult ? (
              <button disabled={submitBusy} onClick={resetSelectedFiles} type="button" className="secondary">
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
          {linkResult ? <p className="helper-text">已加入队列：{linkResult.total} 个任务</p> : null}
          <div className="action-row">
            <button disabled={submitBusy || !link.trim()} onClick={handleCaptureLink} type="button">
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
              已加入队列：{bookmarkResult.total} 个任务
            </p>
          ) : null}
          <div className="action-row">
            <button disabled={submitBusy || !bookmarkHtml.trim()} onClick={handleImportBookmarks} type="button">
              导入书签
            </button>
            {bookmarkResult ? (
              <button
                disabled={submitBusy}
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
