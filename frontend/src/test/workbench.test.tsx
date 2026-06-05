import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'

function jsonResponse(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
  } as Response)
}

describe('Lumen workbench', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'

        if (url.endsWith('/api/sources') && method === 'GET') {
          return jsonResponse([])
        }
        if (url.endsWith('/api/memories/candidates') && method === 'GET') {
          return jsonResponse([
            {
              id: 1,
              text: 'Remember that Lumen needs citations.',
              memory_type: 'project',
              source_kind: 'message',
              source_ref: '1',
              confidence: 72,
              status: 'pending',
              created_at: '2026-06-05T00:00:00',
            },
            {
              id: 2,
              text: 'Ignore this temporary preference.',
              memory_type: 'preference',
              source_kind: 'message',
              source_ref: '2',
              confidence: 72,
              status: 'pending',
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/review') && method === 'GET') {
          return jsonResponse({
            sources_added: [],
            memories_confirmed: [],
            pending_memories: [],
            recent_questions: [],
            suggested_actions: ['Add a source to begin.'],
          })
        }
        if (url.endsWith('/api/chat') && method === 'POST') {
          return jsonResponse({
            conversation_id: 1,
            message_id: 2,
            answer: 'Grounded answer with citation.',
            citations: [{ source_id: 1, source_title: 'Acceptance Note', chunk_id: 1, quote: 'Lumen should cite sources.' }],
            memories: [],
            confidence: 'grounded',
          })
        }
        if (url.endsWith('/api/memories/candidates/1/confirm') && method === 'POST') {
          return jsonResponse({
            id: 1,
            text: 'Remember that Lumen needs citations.',
            memory_type: 'project',
            provenance: 'message:1',
            status: 'active',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/memories/candidates/2/ignore') && method === 'POST') {
          return jsonResponse({ status: 'ignored' })
        }
        throw new Error(`Unhandled request: ${method} ${url}`)
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the workbench and completes the ask and memory review loop', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(screen.getByText('Lumen')).toBeInTheDocument()
    expect(screen.getByText('Ask or capture')).toBeInTheDocument()
    expect(screen.getByText('Memory Inbox')).toBeInTheDocument()
    expect(screen.getByText('Context Now')).toBeInTheDocument()
    expect(screen.getByText('Recent Sources')).toBeInTheDocument()
    expect(screen.getByText('Daily Review')).toBeInTheDocument()

    expect(await screen.findByText('Remember that Lumen needs citations.')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Ask Lumen'), 'What should Lumen cite?')
    await user.click(screen.getByRole('button', { name: 'Ask Lumen' }))

    expect(await screen.findByText('Grounded answer with citation.')).toBeInTheDocument()
    expect(await screen.findByText('Acceptance Note')).toBeInTheDocument()
    expect(screen.getByText('Lumen should cite sources.')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Confirm' })[0])
    await user.click(screen.getAllByRole('button', { name: 'Ignore' })[1])

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/memories/candidates/1/confirm',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/memories/candidates/2/ignore',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
