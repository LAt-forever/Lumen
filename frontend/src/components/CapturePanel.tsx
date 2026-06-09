import { ChangeEvent, FormEvent, useRef, useState } from 'react'

import { useAskLumen, useAskLumenStream, useCaptureLink, useCreateSource, useUploadSource } from '../api/hooks'
import type { ChatResponse } from '../api/types'

type CapturePanelProps = {
  onResponse?: (response: ChatResponse) => void
  onStreamChunk?: (text: string) => void
  onStreamStart?: () => void
}

type CaptureMode = 'note' | 'file' | 'link'

export function CapturePanel({ onResponse, onStreamChunk, onStreamStart }: CapturePanelProps) {
  const [mode, setMode] = useState<CaptureMode>('note')
  const [draft, setDraft] = useState('')
  const [selectedFile, setSelectedFile] = useState<File>()
  const [link, setLink] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const askLumen = useAskLumen()
  const askLumenStream = useAskLumenStream()
  const createSource = useCreateSource()
  const uploadSource = useUploadSource()
  const captureLink = useCaptureLink()

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

  const resetSelectedFile = () => {
    setSelectedFile(undefined)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const uploadSelectedFile = (file: File) => {
    uploadSource.mutate(file, { onSuccess: resetSelectedFile })
  }

  const handleFileSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    setSelectedFile(file)
    if (file) {
      uploadSelectedFile(file)
    }
  }

  const handleUpload = () => {
    if (!selectedFile) {
      fileInputRef.current?.click()
      return
    }
    uploadSelectedFile(selectedFile)
  }

  const handleCaptureLink = () => {
    const url = link.trim()
    if (url) {
      captureLink.mutate(url)
    }
  }

  const isBusy =
    askLumen.isPending || askLumenStream.isPending || createSource.isPending || uploadSource.isPending || captureLink.isPending
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
            accept=".txt,.md,.pdf"
            id="source-file"
            onChange={handleFileSelected}
            ref={fileInputRef}
            type="file"
          />
          <p className="helper-text">
            {selectedFile ? `正在上传：${selectedFile.name}` : '支持 TXT、Markdown、PDF。选择文件后会自动上传。'}
          </p>
          <div className="action-row">
            <button disabled={isBusy} onClick={handleUpload} type="button">
              上传文件
            </button>
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
          <div className="action-row">
            <button disabled={isBusy || !link.trim()} onClick={handleCaptureLink} type="button">
              添加链接
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
