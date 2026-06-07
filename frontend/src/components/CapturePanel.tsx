import { FormEvent, useState } from 'react'

import { useAskLumen, useCreateSource } from '../api/hooks'
import type { ChatResponse } from '../api/types'

type CapturePanelProps = {
  onResponse?: (response: ChatResponse) => void
}

export function CapturePanel({ onResponse }: CapturePanelProps) {
  const [draft, setDraft] = useState('')
  const askLumen = useAskLumen()
  const createSource = useCreateSource()

  const handleAsk = (event: FormEvent) => {
    event.preventDefault()
    const message = draft.trim()
    if (message) {
      askLumen.mutate(message, { onSuccess: (response) => onResponse?.(response) })
    }
  }

  const handleAddSource = () => {
    const content = draft.trim()
    if (content) {
      createSource.mutate({ title: content.slice(0, 72), source_type: 'note', content })
    }
  }

  const isBusy = askLumen.isPending || createSource.isPending

  return (
    <section className="center-panel" aria-label="询问或记录">
      <div className="panel-header">
        <div>
          <p className="eyebrow">主工作区</p>
          <h2>询问或记录</h2>
        </div>
        <span className="mode-pill">{isBusy ? '处理中' : '就绪'}</span>
      </div>
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
          <button disabled={isBusy || !draft.trim()} type="submit">
            询问 Lumen
          </button>
          <button disabled={isBusy || !draft.trim()} onClick={handleAddSource} type="button" className="secondary">
            添加资料
          </button>
        </div>
      </form>
    </section>
  )
}
