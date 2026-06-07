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
              text: '记住 Lumen 需要展示引用。',
              memory_type: 'project',
              source_kind: 'message',
              source_ref: '1',
              confidence: 72,
              status: 'pending',
              created_at: '2026-06-05T00:00:00',
            },
            {
              id: 2,
              text: '忽略这个临时偏好。',
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
            suggested_actions: ['添加一条资料开始使用。'],
          })
        }
        if (url.endsWith('/api/chat') && method === 'POST') {
          return jsonResponse({
            conversation_id: 1,
            message_id: 2,
            answer: '带引用的可信回答。',
            citations: [{ source_id: 1, source_title: '验收笔记', chunk_id: 1, quote: 'Lumen 应该引用资料来源。' }],
            memories: [],
            confidence: 'grounded',
          })
        }
        if (url.endsWith('/api/memories/candidates/1/confirm') && method === 'POST') {
          return jsonResponse({
            id: 1,
            text: '记住 Lumen 需要展示引用。',
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
    expect(screen.getByText('询问或记录')).toBeInTheDocument()
    expect(screen.getByText('记忆收件箱')).toBeInTheDocument()
    expect(screen.getByText('当前上下文')).toBeInTheDocument()
    expect(screen.getByText('最近资料')).toBeInTheDocument()
    expect(screen.getByText('今日回顾')).toBeInTheDocument()

    expect(await screen.findByText('记住 Lumen 需要展示引用。')).toBeInTheDocument()

    await user.type(screen.getByLabelText('询问 Lumen'), 'Lumen 应该引用什么？')
    await user.click(screen.getByRole('button', { name: '询问 Lumen' }))

    expect(await screen.findByText('带引用的可信回答。')).toBeInTheDocument()
    expect(await screen.findByText('验收笔记')).toBeInTheDocument()
    expect(screen.getByText('Lumen 应该引用资料来源。')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: '确认' })[0])
    await user.click(screen.getAllByRole('button', { name: '忽略' })[1])

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
