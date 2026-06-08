import { cleanup, render, screen } from '@testing-library/react'
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
          return jsonResponse([
            {
              id: 7,
              title: '已有资料',
              source_type: 'note',
              status: 'indexed',
              url: null,
              filename: null,
              error_message: null,
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/sources/upload') && method === 'POST') {
          return jsonResponse({
            id: 8,
            title: 'phase-1-1.txt',
            source_type: 'text',
            status: 'pending',
            url: null,
            filename: 'phase-1-1.txt',
            error_message: null,
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/sources/link') && method === 'POST') {
          return jsonResponse({
            id: 9,
            title: 'https://example.com/lumen',
            source_type: 'link',
            status: 'pending',
            url: 'https://example.com/lumen',
            filename: null,
            error_message: null,
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/sources/8/index') && method === 'POST') {
          return jsonResponse({
            id: 8,
            title: 'phase-1-1.txt',
            source_type: 'text',
            status: 'indexed',
            url: null,
            filename: 'phase-1-1.txt',
            error_message: null,
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/sources/9/index') && method === 'POST') {
          return jsonResponse({
            id: 9,
            title: 'https://example.com/lumen',
            source_type: 'link',
            status: 'indexed',
            url: 'https://example.com/lumen',
            filename: null,
            error_message: null,
            created_at: '2026-06-05T00:00:00',
          })
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
        if (url.endsWith('/api/memories') && method === 'GET') {
          return jsonResponse([
            {
              id: 10,
              text: '用户喜欢引用清楚的回答。',
              memory_type: 'preference',
              provenance: 'message:1',
              status: 'active',
              created_at: '2026-06-05T00:00:00',
            },
            {
              id: 11,
              text: 'Lumen 是当前个人知识库项目。',
              memory_type: 'project',
              provenance: 'message:2',
              status: 'active',
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
        if (url.endsWith('/api/settings/runtime') && method === 'GET') {
          return jsonResponse({
            llm_mode: 'llm',
            llm_provider: 'openai-compatible',
            llm_model: 'gpt-test',
            llm_configured: true,
            llm_fallback_enabled: true,
            embedding_mode: 'hash',
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
            answer_mode: 'llm',
            fallback_reason: null,
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
        if (url.endsWith('/api/search?q=link+capture') && method === 'GET') {
          return jsonResponse([
            {
              id: 3,
              source_id: 9,
              source_title: 'https://example.com/lumen',
              text: 'Lumen link capture should be searchable.',
              score: 4.2,
            },
          ])
        }
        if (url.endsWith('/api/memories/10') && method === 'PATCH') {
          return jsonResponse({
            id: 10,
            text: '用户偏好带清晰引用的回答。',
            memory_type: 'preference',
            provenance: 'message:1',
            status: 'edited',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/memories/10/forget') && method === 'POST') {
          return jsonResponse({
            id: 10,
            text: '用户偏好带清晰引用的回答。',
            memory_type: 'preference',
            provenance: 'message:1',
            status: 'forgotten',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/memories/11/merge') && method === 'POST') {
          return jsonResponse({
            id: 10,
            text: '用户偏好带清晰引用的回答。 Lumen 是当前个人知识库项目。',
            memory_type: 'preference',
            provenance: 'message:1',
            status: 'edited',
            created_at: '2026-06-05T00:00:00',
          })
        }
        throw new Error(`Unhandled request: ${method} ${url}`)
      }),
    )
  })

  afterEach(() => {
    cleanup()
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
    expect((await screen.findAllByText('LLM 模式')).length).toBeGreaterThan(0)
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

  it('supports Phase 1.1 source, search, and confirmed memory workflows', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '资料库' }))
    await user.click(screen.getByRole('button', { name: '文件' }))
    const file = new File(['Lumen Phase 1.1 file upload.'], 'phase-1-1.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText('选择资料文件'), file)
    await user.click(screen.getByRole('button', { name: '上传文件' }))

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/sources/upload',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '链接' }))
    await user.type(screen.getByLabelText('网页链接'), 'https://example.com/lumen')
    await user.click(screen.getByRole('button', { name: '添加链接' }))

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/sources/link',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '搜索' }))
    await user.type(screen.getByLabelText('搜索资料'), 'link capture')
    await user.click(screen.getByRole('button', { name: '执行搜索' }))

    expect(await screen.findByText('Lumen link capture should be searchable.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '记忆' }))
    expect(await screen.findByText('用户喜欢引用清楚的回答。')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: '编辑' })[0])
    await user.clear(screen.getByLabelText('记忆内容'))
    await user.type(screen.getByLabelText('记忆内容'), '用户偏好带清晰引用的回答。')
    await user.click(screen.getByRole('button', { name: '保存记忆' }))

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/memories/10',
      expect.objectContaining({ method: 'PATCH' }),
    )

    await user.click(screen.getAllByRole('button', { name: '遗忘' })[0])
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/memories/10/forget',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.selectOptions(screen.getByLabelText('合并目标 11'), '10')
    await user.click(screen.getAllByRole('button', { name: '合并到目标' })[1])
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/memories/11/merge',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '设置' }))
    expect(await screen.findByText('openai-compatible')).toBeInTheDocument()
    expect(screen.getByText('gpt-test')).toBeInTheDocument()
    expect(screen.getByText('API key 已配置')).toBeInTheDocument()
  })
})
