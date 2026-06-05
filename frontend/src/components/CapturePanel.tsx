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
    <section className="center-panel" aria-label="Ask or capture">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Primary workspace</p>
          <h2>Ask or capture</h2>
        </div>
        <span className="mode-pill">{isBusy ? 'Working' : 'Ready'}</span>
      </div>
      <form onSubmit={handleAsk}>
        <label className="field-label" htmlFor="ask-lumen">
          Ask a question, write a note, or paste a link
        </label>
        <textarea
          id="ask-lumen"
          aria-label="Ask Lumen"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="What should I remember from this source?"
          value={draft}
        />
        <div className="action-row">
          <button disabled={isBusy || !draft.trim()} type="submit">
            Ask Lumen
          </button>
          <button disabled={isBusy || !draft.trim()} onClick={handleAddSource} type="button" className="secondary">
            Add source
          </button>
        </div>
      </form>
    </section>
  )
}
