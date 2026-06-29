import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'

vi.mock('@xyflow/react', () => ({
  ReactFlow: () => null,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  Handle: () => null,
  Position: { Top: 'top', Bottom: 'bottom' },
}))

function jsonResponse(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
  } as Response)
}

function noContentResponse() {
  return Promise.resolve({
    ok: true,
    status: 204,
    json: () => Promise.resolve(undefined),
  } as Response)
}

function streamResponse(text: string) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text))
      controller.close()
    },
  })
  return Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
}

function deferredStreamResponse() {
  const encoder = new TextEncoder()
  let controllerRef: ReadableStreamDefaultController<Uint8Array> | undefined
  const stream = new ReadableStream({
    start(controller) {
      controllerRef = controller
    },
  })
  const push = (text: string) => controllerRef?.enqueue(encoder.encode(text))
  const close = () => controllerRef?.close()
  return {
    response: Promise.resolve(new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })),
    push,
    close,
  }
}

function deferredRejectedResponse() {
  let rejectRef: ((reason?: unknown) => void) | undefined
  const response = new Promise<Response>((_resolve, reject) => {
    rejectRef = reject
  })
  return {
    response,
    reject: () => rejectRef?.(new Error('stream failed after switch')),
  }
}

describe('Lumen workbench', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem('lumen.accessToken', 'test-token')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'

        if (url.endsWith('/api/auth/me') && method === 'GET') {
          return jsonResponse({
            id: 1,
            email: 'admin@example.com',
            is_admin: true,
            created_at: '2026-06-29T00:00:00',
          })
        }
        if (url.endsWith('/api/auth/login') && method === 'POST') {
          return jsonResponse({
            access_token: 'login-token',
            token_type: 'bearer',
            user: {
              id: 2,
              email: 'lanhe@example.com',
              is_admin: false,
              created_at: '2026-06-29T00:00:00',
            },
          })
        }
        if (url.endsWith('/api/knowledge-bases') && method === 'GET') {
          return jsonResponse([
            {
              id: 1,
              name: '默认知识库',
              description: '默认收集箱',
              status: 'active',
              is_default: true,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:00',
            },
            {
              id: 2,
              name: '项目知识库',
              description: '项目资料',
              status: 'active',
              is_default: false,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:00',
            },
            {
              id: 3,
              name: '归档知识库',
              description: '旧资料',
              status: 'archived',
              is_default: false,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/knowledge-bases') && method === 'POST') {
          return jsonResponse({
            id: 4,
            name: '新知识库',
            description: '新的资料范围',
            status: 'active',
            is_default: false,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/knowledge-bases/2') && method === 'PATCH') {
          return jsonResponse({
            id: 2,
            name: '项目资料库',
            description: '更新后的项目资料',
            status: 'active',
            is_default: false,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:01',
          })
        }
        if (url.endsWith('/api/knowledge-bases/2/archive') && method === 'POST') {
          return jsonResponse({
            id: 2,
            name: '项目知识库',
            description: '项目资料',
            status: 'archived',
            is_default: false,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:01',
          })
        }
        if (url.endsWith('/api/knowledge-bases/3/restore') && method === 'POST') {
          return jsonResponse({
            id: 3,
            name: '归档知识库',
            description: '旧资料',
            status: 'active',
            is_default: false,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:01',
          })
        }
        if (url.endsWith('/api/knowledge-bases/3') && method === 'DELETE') {
          return noContentResponse()
        }
        if ((url.endsWith('/api/sources') || url.includes('/api/sources?')) && method === 'GET') {
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
        if (url.endsWith('/api/sources/7') && method === 'GET') {
          return jsonResponse({
            id: 7,
            title: '已有资料',
            source_type: 'note',
            status: 'indexed',
            url: null,
            filename: null,
            error_message: null,
            created_at: '2026-06-05T00:00:00',
            chunk_count: 2,
          })
        }
        if (url.endsWith('/api/sources/7') && method === 'DELETE') {
          return noContentResponse()
        }
        if (url.includes('/api/ingestion-jobs') && method === 'GET') {
          return jsonResponse([
            {
              id: 101,
              batch_id: 'batch-active',
              source_id: 8,
              source_title: 'phase-1-1.txt',
              job_type: 'upload',
              status: 'running',
              progress_current: 1,
              progress_total: 3,
              message: '正在解析资料',
              error_message: null,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:01',
              started_at: '2026-06-05T00:00:01',
              finished_at: null,
            },
            {
              id: 102,
              batch_id: 'batch-failed',
              source_id: 12,
              source_title: '失败链接',
              job_type: 'link',
              status: 'failed',
              progress_current: 1,
              progress_total: 3,
              message: '正在解析资料',
              error_message: 'temporary link failure',
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:02',
              started_at: '2026-06-05T00:00:01',
              finished_at: '2026-06-05T00:00:02',
            },
          ])
        }
        if (url.endsWith('/api/ingestion-jobs/notes') && method === 'POST') {
          return jsonResponse({
            batch_id: 'batch-note',
            total: 1,
            queued: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            canceled: 0,
            jobs: [
              {
                id: 100,
                batch_id: 'batch-note',
                source_id: 20,
                source_title: 'Lumen queued note',
                job_type: 'note',
                status: 'queued',
                progress_current: 0,
                progress_total: 3,
                message: '已加入队列',
                error_message: null,
                created_at: '2026-06-05T00:00:00',
                updated_at: '2026-06-05T00:00:00',
                started_at: null,
                finished_at: null,
              },
            ],
            sources: [],
          })
        }
        if (url.includes('/api/ingestion-jobs/uploads') && method === 'POST') {
          return jsonResponse({
            batch_id: 'batch-upload',
            total: 1,
            queued: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            canceled: 0,
            jobs: [
              {
                id: 101,
                batch_id: 'batch-upload',
                source_id: 8,
                source_title: 'phase-1-1.txt',
                job_type: 'upload',
                status: 'queued',
                progress_current: 0,
                progress_total: 3,
                message: '已加入队列',
                error_message: null,
                created_at: '2026-06-05T00:00:00',
                updated_at: '2026-06-05T00:00:00',
                started_at: null,
                finished_at: null,
              },
            ],
            sources: [],
          })
        }
        if (url.endsWith('/api/ingestion-jobs/links') && method === 'POST') {
          return jsonResponse({
            batch_id: 'batch-link',
            total: 1,
            queued: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            canceled: 0,
            jobs: [
              {
                id: 103,
                batch_id: 'batch-link',
                source_id: 9,
                source_title: 'https://example.com/lumen',
                job_type: 'link',
                status: 'queued',
                progress_current: 0,
                progress_total: 3,
                message: '已加入队列',
                error_message: null,
                created_at: '2026-06-05T00:00:00',
                updated_at: '2026-06-05T00:00:00',
                started_at: null,
                finished_at: null,
              },
            ],
            sources: [],
          })
        }
        if (url.endsWith('/api/ingestion-jobs/crawls') && method === 'POST') {
          return jsonResponse({
            batch_id: 'batch-crawl',
            total: 1,
            queued: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            canceled: 0,
            jobs: [
              {
                id: 104,
                batch_id: 'batch-crawl',
                source_id: 10,
                source_title: 'https://example.com/crawl',
                job_type: 'crawl',
                status: 'queued',
                progress_current: 0,
                progress_total: 3,
                message: '已加入队列',
                error_message: null,
                created_at: '2026-06-05T00:00:00',
                updated_at: '2026-06-05T00:00:00',
                started_at: null,
                finished_at: null,
              },
            ],
            sources: [],
          })
        }
        if (url.endsWith('/api/ingestion-jobs/bookmarks') && method === 'POST') {
          return jsonResponse({
            batch_id: 'batch-bookmark',
            total: 1,
            queued: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            canceled: 0,
            jobs: [
              {
                id: 105,
                batch_id: 'batch-bookmark',
                source_id: 11,
                source_title: 'Example Bookmark',
                job_type: 'bookmark',
                status: 'queued',
                progress_current: 0,
                progress_total: 3,
                message: '已加入队列',
                error_message: null,
                created_at: '2026-06-05T00:00:00',
                updated_at: '2026-06-05T00:00:00',
                started_at: null,
                finished_at: null,
              },
            ],
            sources: [],
          })
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
            configuration_hint: 'LLM 模式已开启，但模型名称或 API key 未配置。',
            latest_fallback_reason: null,
            runtime_source: 'environment',
            active_profile_id: null,
            active_profile_name: null,
          })
        }
        if (url.endsWith('/api/settings/provider-profiles') && method === 'GET') {
          return jsonResponse([
            {
              id: 21,
              name: '备用模型',
              provider: 'openai-compatible',
              base_url: 'https://backup.example/v1',
              model: 'gpt-backup',
              api_key_configured: true,
              timeout_seconds: 12,
              fallback_enabled: true,
              is_active: false,
              supports_chat: true,
              supports_embedding: false,
              embedding_model: null,
              embedding_dimensions: null,
              embedding_status: 'untested',
              embedding_last_error: null,
              embedding_last_checked_at: null,
              status: 'untested',
              last_error: null,
              last_checked_at: null,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/agent/profiles') && method === 'GET') {
          return jsonResponse([
            {
              id: 71,
              name: '只读研究 Agent',
              instructions: '只使用已授权的只读工具；证据不足时说明不知道。',
              enabled_tools: ['global_search', 'memory_search'],
              require_approval: true,
              is_active: true,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/agent/profiles') && method === 'POST') {
          return jsonResponse({
            id: 72,
            name: '只读研究 Agent',
            instructions: '只使用已授权的只读工具；证据不足时说明不知道。',
            enabled_tools: ['global_search', 'memory_search'],
            require_approval: true,
            is_active: true,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/agent/runs') && method === 'POST') {
          return jsonResponse({
            answer: '我运行了 全局搜索、记忆搜索。最相关资料是「全局搜索资料」。',
            used_tools: ['global_search', 'memory_search'],
            search_results: [],
            memories: [],
            graph: null,
            tool_logs: [
              {
                id: 81,
                profile_id: 71,
                tool_name: 'global_search',
                action: 'search',
                input_json: '{"query":"Phase15"}',
                result_summary: '返回 1 条结果',
                status: 'succeeded',
                error_message: null,
                created_at: '2026-06-05T00:00:00',
              },
            ],
          })
        }
        if (url.endsWith('/api/agent/tool-logs') && method === 'GET') {
          return jsonResponse([
            {
              id: 81,
              profile_id: 71,
              tool_name: 'global_search',
              action: 'search',
              input_json: '{"query":"Phase15"}',
              result_summary: '返回 1 条结果',
              status: 'succeeded',
              error_message: null,
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/agent/reranker-profiles') && method === 'GET') {
          return jsonResponse([
            {
              id: 91,
              name: '外部 reranker',
              provider: 'openai-compatible',
              base_url: 'https://rerank.example/v1',
              model: 'rerank-test',
              api_key_configured: true,
              top_n: 20,
              is_active: true,
              status: 'configured',
              last_error: null,
              created_at: '2026-06-05T00:00:00',
              updated_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/agent/reranker-profiles') && method === 'POST') {
          return jsonResponse({
            id: 92,
            name: '外部 reranker',
            provider: 'openai-compatible',
            base_url: 'https://rerank.example/v1',
            model: 'rerank-test',
            api_key_configured: true,
            top_n: 20,
            is_active: true,
            status: 'configured',
            last_error: null,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/tags') && method === 'GET') {
          return jsonResponse([
            {
              id: 31,
              name: 'Phase15',
              color: '#2563eb',
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/tag-suggestions') && method === 'GET') {
          return jsonResponse([
            {
              id: 41,
              label: 'Phase15',
              target_type: 'source',
              target_id: 7,
              reason: '从资料「已有资料」中识别到标签线索。',
              confidence: 72,
              status: 'pending',
              created_at: '2026-06-05T00:00:00',
            },
            {
              id: 42,
              label: '偏好',
              target_type: 'memory',
              target_id: 10,
              reason: '从已确认记忆中识别到标签线索。',
              confidence: 70,
              status: 'pending',
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/tag-suggestions/41/confirm') && method === 'POST') {
          return jsonResponse({
            id: 51,
            tag: { id: 31, name: 'Phase15', color: '#2563eb', created_at: '2026-06-05T00:00:00' },
            target_type: 'source',
            target_id: 7,
            source: 'ai-confirmed',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/tag-suggestions/42/ignore') && method === 'POST') {
          return jsonResponse({
            id: 42,
            label: '偏好',
            target_type: 'memory',
            target_id: 10,
            reason: '从已确认记忆中识别到标签线索。',
            confidence: 70,
            status: 'ignored',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/tags/assignments') && method === 'POST') {
          return jsonResponse({
            id: 52,
            tag: { id: 31, name: 'Phase15', color: '#2563eb', created_at: '2026-06-05T00:00:00' },
            target_type: 'source',
            target_id: 7,
            source: 'user',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/favorites') && method === 'GET') {
          return jsonResponse([])
        }
        if (url.endsWith('/api/favorites') && method === 'POST') {
          return jsonResponse({
            id: 61,
            target_type: 'source',
            target_id: 7,
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/favorites/source/7') && method === 'DELETE') {
          return noContentResponse()
        }
        if (url.endsWith('/api/favorites/message/2') && method === 'DELETE') {
          return noContentResponse()
        }
        if (url.includes('/api/global-search') && url.includes('link+capture') && method === 'GET') {
          return jsonResponse([
            {
              result_type: 'source_chunk',
              target_id: 3,
              title: 'https://example.com/lumen',
              snippet: 'Lumen link capture should be searchable.',
              score: 4.2,
              matched_terms: ['capture', 'link'],
              matched_date: null,
              match_reason: '匹配关键词：capture、link',
              tags: [],
              is_favorite: false,
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.includes('/api/global-search') && method === 'GET') {
          return jsonResponse([
            {
              result_type: 'source_chunk',
              target_id: 3,
              title: '全局搜索资料',
              snippet: 'Phase15 全局搜索应该返回资料片段。',
              score: 5.2,
              matched_terms: ['phase15', '搜索'],
              matched_date: null,
              match_reason: '匹配关键词：phase15、搜索',
              tags: [{ id: 31, name: 'Phase15', color: '#2563eb', created_at: '2026-06-05T00:00:00' }],
              is_favorite: false,
              created_at: '2026-06-05T00:00:00',
            },
            {
              result_type: 'memory',
              target_id: 10,
              title: '记忆：preference',
              snippet: '用户喜欢引用清楚的回答。',
              score: 4.4,
              matched_terms: ['引用'],
              matched_date: null,
              match_reason: '匹配关键词：引用',
              tags: [],
              is_favorite: true,
              created_at: '2026-06-05T00:00:00',
            },
            {
              result_type: 'message',
              target_id: 2,
              title: '回答 #2',
              snippet: '带引用的可信回答。',
              score: 3.3,
              matched_terms: ['引用'],
              matched_date: null,
              match_reason: '匹配关键词：引用；已收藏',
              tags: [],
              is_favorite: true,
              created_at: '2026-06-05T00:00:00',
            },
          ])
        }
        if (url.endsWith('/api/status') && method === 'GET') {
          return jsonResponse({
            runtime: {
              llm_mode: 'llm',
              llm_provider: 'openai-compatible',
              llm_model: 'gpt-test',
              llm_configured: true,
              llm_fallback_enabled: true,
              embedding_mode: 'hash',
              configuration_hint: null,
              latest_fallback_reason: null,
              runtime_source: 'environment',
              active_profile_id: null,
              active_profile_name: null,
            },
            services: [
              {
                name: 'postgres',
                label: 'PostgreSQL',
                status: 'ok',
                detail: 'SELECT 1 succeeded',
                latency_ms: 1.2,
                checked_at: '2026-06-22T00:00:00Z',
              },
              {
                name: 'redis',
                label: 'Redis',
                status: 'ok',
                detail: 'PING succeeded',
                latency_ms: 2.3,
                checked_at: '2026-06-22T00:00:00Z',
              },
              {
                name: 'elasticsearch',
                label: 'Elasticsearch',
                status: 'unavailable',
                detail: 'connection refused',
                latency_ms: null,
                checked_at: '2026-06-22T00:00:00Z',
              },
              {
                name: 'neo4j',
                label: 'Neo4j',
                status: 'unavailable',
                detail: 'connection refused',
                latency_ms: null,
                checked_at: '2026-06-22T00:00:00Z',
              },
              {
                name: 'worker',
                label: 'Celery Worker',
                status: 'unavailable',
                detail: 'no worker replied',
                latency_ms: null,
                checked_at: '2026-06-22T00:00:00Z',
              },
              {
                name: 'beat',
                label: 'Celery Beat',
                status: 'unavailable',
                detail: 'heartbeat file not found',
                latency_ms: null,
                checked_at: '2026-06-22T00:00:00Z',
              },
            ],
            source_counts: { total: 2, indexed: 1, failed: 1, pending: 0, parsing: 0 },
            ingestion_jobs: { queued: 0, running: 1, succeeded: 0, failed: 1, canceled: 0 },
            failed_sources: [
              {
                id: 12,
                title: '失败链接',
                source_type: 'link',
                error_message: 'temporary link failure',
                created_at: '2026-06-05T00:00:00',
              },
            ],
            pending_tag_suggestion_count: 2,
            latest_fallback_reason: null,
            suggested_actions: [
              { label: '重试 1 个失败资料', target_view: 'library', target_id: null },
              { label: '确认 2 个标签建议', target_view: 'status', target_id: null },
            ],
          })
        }
        if (url.endsWith('/api/ingestion-jobs/101/cancel') && method === 'POST') {
          return jsonResponse({
            id: 101,
            batch_id: 'batch-active',
            source_id: 8,
            source_title: 'phase-1-1.txt',
            job_type: 'upload',
            status: 'canceled',
            progress_current: 1,
            progress_total: 3,
            message: '已取消',
            error_message: null,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:02',
            started_at: null,
            finished_at: '2026-06-05T00:00:02',
          })
        }
        if (url.endsWith('/api/ingestion-jobs/102/retry') && method === 'POST') {
          return jsonResponse({
            batch_id: 'batch-retry',
            total: 1,
            queued: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            canceled: 0,
            jobs: [],
            sources: [],
          })
        }
        if (url.endsWith('/api/sources/12/retry') && method === 'POST') {
          return jsonResponse({
            id: 12,
            title: '失败链接',
            source_type: 'link',
            status: 'indexed',
            url: 'https://example.com/retry',
            filename: null,
            error_message: null,
            created_at: '2026-06-05T00:00:00',
            chunk_count: 1,
          })
        }
        if (url.endsWith('/api/settings/provider-profiles') && method === 'POST') {
          return jsonResponse({
            id: 22,
            name: '主力模型',
            provider: 'openai-compatible',
            base_url: 'https://model.example/v1',
            model: 'gpt-main',
            api_key_configured: true,
              timeout_seconds: 20,
              fallback_enabled: true,
              is_active: false,
              supports_chat: true,
              supports_embedding: true,
              embedding_model: 'text-embedding-3-small',
              embedding_dimensions: 1536,
              embedding_status: 'untested',
              embedding_last_error: null,
              embedding_last_checked_at: null,
              status: 'untested',
              last_error: null,
              last_checked_at: null,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/settings/provider-profiles/21/test') && method === 'POST') {
          return jsonResponse({
            id: 21,
            name: '备用模型',
            provider: 'openai-compatible',
            base_url: 'https://backup.example/v1',
            model: 'gpt-backup',
            api_key_configured: true,
              timeout_seconds: 12,
              fallback_enabled: true,
              is_active: false,
              supports_chat: true,
              supports_embedding: false,
              embedding_model: null,
              embedding_dimensions: null,
              embedding_status: 'untested',
              embedding_last_error: null,
              embedding_last_checked_at: null,
              status: 'ready',
              last_error: null,
              last_checked_at: '2026-06-05T00:00:00',
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/settings/provider-profiles/21/activate') && method === 'POST') {
          return jsonResponse({
            id: 21,
            name: '备用模型',
            provider: 'openai-compatible',
            base_url: 'https://backup.example/v1',
            model: 'gpt-backup',
            api_key_configured: true,
              timeout_seconds: 12,
              fallback_enabled: true,
              is_active: true,
              supports_chat: true,
              supports_embedding: false,
              embedding_model: null,
              embedding_dimensions: null,
              embedding_status: 'untested',
              embedding_last_error: null,
              embedding_last_checked_at: null,
              status: 'ready',
              last_error: null,
              last_checked_at: '2026-06-05T00:00:00',
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:00',
          })
        }
        if (url.endsWith('/api/settings/provider-profiles/21') && method === 'PATCH') {
          return jsonResponse({
            id: 21,
            name: '备用模型',
            provider: 'openai-compatible',
            base_url: 'https://backup.example/v1',
            model: 'gpt-backup',
            api_key_configured: true,
            timeout_seconds: 12,
            fallback_enabled: true,
            is_active: false,
            supports_chat: true,
            supports_embedding: true,
            embedding_model: 'text-embedding-3-small',
            embedding_dimensions: 1536,
            embedding_status: 'untested',
            embedding_last_error: null,
            embedding_last_checked_at: null,
            status: 'untested',
            last_error: null,
            last_checked_at: null,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:01',
          })
        }
        if (url.endsWith('/api/settings/provider-profiles/21/test-embedding') && method === 'POST') {
          return jsonResponse({
            id: 21,
            name: '备用模型',
            provider: 'openai-compatible',
            base_url: 'https://backup.example/v1',
            model: 'gpt-backup',
            api_key_configured: true,
            timeout_seconds: 12,
            fallback_enabled: true,
            is_active: false,
            supports_chat: true,
            supports_embedding: true,
            embedding_model: 'text-embedding-3-small',
            embedding_dimensions: 1536,
            embedding_status: 'ready',
            embedding_last_error: null,
            embedding_last_checked_at: '2026-06-05T00:00:00',
            status: 'untested',
            last_error: null,
            last_checked_at: null,
            created_at: '2026-06-05T00:00:00',
            updated_at: '2026-06-05T00:00:01',
          })
        }
        if (url.endsWith('/api/chat') && method === 'POST') {
          return jsonResponse({
            conversation_id: 1,
            message_id: 2,
            answer: '带引用的可信回答。',
            citations: [
              {
                source_id: 1,
                source_title: '验收笔记',
                chunk_id: 1,
                quote: 'Lumen 应该引用资料来源。',
                matched_terms: ['Lumen', '引用'],
                matched_date: null,
                match_reason: '匹配关键词：Lumen、引用',
                retrieval_mode: 'es_hybrid',
                retrieval_source: 'local_fallback',
              },
            ],
            memories: [],
            confidence: 'grounded',
            answer_mode: 'llm',
            fallback_reason: null,
          })
        }
        if (url.endsWith('/api/chat/stream') && method === 'POST') {
          return streamResponse(
            [
              'event: chunk',
              'data: {"text":"带引用的"}',
              '',
              'event: chunk',
              'data: {"text":"可信回答。"}',
              '',
              'event: final',
              'data: {"conversation_id":1,"message_id":2,"answer":"带引用的可信回答。","citations":[{"source_id":1,"source_title":"验收笔记","chunk_id":1,"quote":"Lumen 应该引用资料来源。","matched_terms":["Lumen","引用"],"matched_date":null,"match_reason":"匹配关键词：Lumen、引用","retrieval_mode":"es_hybrid","retrieval_source":"local_fallback"}],"memories":[],"confidence":"grounded","answer_mode":"llm","fallback_reason":null}',
              '',
            ].join('\n'),
          )
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
        if (url.includes('/api/search?') && url.includes('q=link+capture') && method === 'GET') {
          return jsonResponse([
            {
              id: 3,
              source_id: 9,
              source_title: 'https://example.com/lumen',
              text: 'Lumen link capture should be searchable.',
              score: 4.2,
              matched_terms: ['capture', 'link'],
              matched_date: null,
              match_reason: '匹配关键词：capture、link',
            },
          ])
        }
        if (url.endsWith('/api/memories/duplicate-suggestions') && method === 'GET') {
          return jsonResponse([
            {
              source_memory_id: 11,
              target_memory_id: 10,
              source_text: 'Lumen 是当前个人知识库项目。',
              target_text: '用户喜欢引用清楚的回答。',
              overlap_score: 0.72,
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
        if (url.includes('/api/memories/') && url.includes('/graph') && method === 'GET') {
          return jsonResponse({
            center_memory_id: 10,
            nodes: [
              { id: 10, text: '用户喜欢引用清楚的回答。', memory_type: 'preference', status: 'active' },
              { id: 11, text: 'Lumen 是当前个人知识库项目。', memory_type: 'project', status: 'active' },
            ],
            edges: [
              {
                id: 100,
                source_memory_id: 10,
                target_memory_id: 11,
                relation_type: 'related_to',
                provenance: 'user',
                strength: 72,
                status: 'active',
              },
            ],
          })
        }
        if (url.includes('/api/memories/') && url.includes('/relations') && method === 'GET') {
          return jsonResponse([])
        }
        if (url.includes('/api/memories/') && url.includes('/relations') && method === 'POST') {
          return jsonResponse({
            id: 101,
            source_memory_id: 10,
            target_memory_id: 11,
            relation_type: 'related_to',
            provenance: 'user',
            strength: 70,
            status: 'active',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.includes('/api/memories/') && url.includes('/relations/') && url.includes('/forget') && method === 'POST') {
          return jsonResponse({
            id: 100,
            source_memory_id: 10,
            target_memory_id: 11,
            relation_type: 'related_to',
            provenance: 'user',
            strength: 72,
            status: 'forgotten',
            created_at: '2026-06-05T00:00:00',
          })
        }
        if (url.includes('/api/memories/duplicate-suggestions/') && url.includes('/relate') && method === 'POST') {
          return jsonResponse({
            id: 102,
            source_memory_id: 11,
            target_memory_id: 10,
            relation_type: 'related_to',
            provenance: 'user',
            strength: 72,
            status: 'active',
            created_at: '2026-06-05T00:00:00',
          })
        }
        throw new Error(`Unhandled request: ${method} ${url}`)
      }),
    )
  })

  afterEach(() => {
    cleanup()
    window.localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('shows the login page when no access token exists', () => {
    window.localStorage.removeItem('lumen.accessToken')

    render(<App />)

    expect(screen.getByRole('heading', { name: '登录 Lumen' })).toBeInTheDocument()
    expect(screen.getByLabelText('邮箱')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
  })

  it('logs in and opens the workbench', async () => {
    const user = userEvent.setup()
    window.localStorage.removeItem('lumen.accessToken')

    render(<App />)

    await user.type(screen.getByLabelText('邮箱'), 'lanhe@example.com')
    await user.type(screen.getByLabelText('密码'), 'test-password')
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByText('询问或记录')).toBeInTheDocument()
    expect(window.localStorage.getItem('lumen.accessToken')).toBe('login-token')
  })

  it('sends the bearer token with API requests', async () => {
    render(<App />)

    await screen.findByText('询问或记录')
    const sourceRequest = vi.mocked(fetch).mock.calls.find(([url]) => String(url).includes('/api/sources'))

    expect(sourceRequest?.[1]).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      }),
    )
  })

  it('preserves stored active knowledge base after knowledge bases load', async () => {
    window.localStorage.setItem('lumen.activeKnowledgeBaseId', '2')

    render(<App />)

    const selector = await screen.findByLabelText('知识库')
    await waitFor(() => expect(selector).toHaveValue('2'))
    expect(window.localStorage.getItem('lumen.activeKnowledgeBaseId')).toBe('2')
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/sources?knowledge_base_id=2',
        expect.objectContaining({ method: 'GET' }),
      ),
    )
    const sourceUrls = vi.mocked(fetch).mock.calls.map(([url]) => String(url)).filter((url) => url.includes('/api/sources'))
    expect(sourceUrls).not.toContain('http://127.0.0.1:8000/api/sources')
  })

  it('does not fetch ingestion jobs without a resolved knowledge base on initial load', async () => {
    render(<App />)

    await screen.findByText('询问或记录')
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/ingestion-jobs?limit=4&knowledge_base_id=1',
        expect.objectContaining({ method: 'GET' }),
      ),
    )
    const jobUrls = vi.mocked(fetch).mock.calls.map(([url]) => String(url)).filter((url) => url.includes('/api/ingestion-jobs?'))
    expect(jobUrls).not.toContain('http://127.0.0.1:8000/api/ingestion-jobs?limit=4')
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
    expect(screen.getByText('匹配关键词：Lumen、引用')).toBeInTheDocument()
    expect(screen.getByText('检索：local_fallback')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('知识库'), '2')
    await waitFor(() => expect(screen.queryByText('带引用的可信回答。')).not.toBeInTheDocument())
    expect(screen.queryByText('验收笔记')).not.toBeInTheDocument()
    expect(screen.queryByText('Lumen 应该引用资料来源。')).not.toBeInTheDocument()

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
    await user.click(screen.getByRole('button', { name: '查看详情' }))
    expect(await screen.findByText('索引片段：2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '删除资料' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/sources/7',
      expect.objectContaining({ method: 'DELETE' }),
    )

    await user.click(screen.getByRole('button', { name: '文件' }))
    const file = new File(['Lumen Phase 1.1 file upload.'], 'phase-1-1.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText('选择资料文件'), file)
    await user.click(screen.getByRole('button', { name: '上传文件' }))

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('http://127.0.0.1:8000/api/ingestion-jobs/uploads'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(await screen.findByText('已加入队列：1 个任务')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '链接' }))
    await user.type(screen.getByLabelText('网页链接'), 'https://example.com/lumen')
    await user.click(screen.getByRole('button', { name: '添加链接' }))

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/links',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '搜索' }))
    await user.type(screen.getByLabelText('全局搜索'), 'link capture')
    await user.click(screen.getByRole('button', { name: '执行搜索' }))

    expect(await screen.findByText('Lumen link capture should be searchable.')).toBeInTheDocument()
    expect(screen.getByText('匹配关键词：capture、link')).toBeInTheDocument()

    await user.click(within(screen.getByRole('navigation', { name: '主导航' })).getByRole('button', { name: '记忆' }))
    expect(await screen.findByText('用户喜欢引用清楚的回答。')).toBeInTheDocument()
    expect(screen.getByText('来源：message:1')).toBeInTheDocument()
    expect(await screen.findByText('可能重复记忆')).toBeInTheDocument()
    expect(screen.getByText('相似度：0.72')).toBeInTheDocument()

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
    expect(screen.getByText('LLM 模式已开启，但模型名称或 API key 未配置。')).toBeInTheDocument()
  })

  it('starts file upload when a file is selected', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '文件' }))

    expect(screen.getByRole('button', { name: '选择文件' })).toBeEnabled()

    const file = new File(['Lumen immediate upload check.'], 'instant-upload.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText('选择资料文件'), file)

    // Multi-file mode: selecting a file shows count but does not auto-upload
    expect(screen.getByText('已选择 1 个文件')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '上传文件' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: '上传文件' }))

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('http://127.0.0.1:8000/api/ingestion-jobs/uploads'),
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    expect(await screen.findByText('已加入队列：1 个任务')).toBeInTheDocument()
  })

  it('manages SQLite-backed model provider profiles from settings', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '设置' }))

    expect(await screen.findByText('备用模型')).toBeInTheDocument()
    expect(screen.getByText('gpt-backup')).toBeInTheDocument()

    await user.type(screen.getByLabelText('配置名称'), '主力模型')
    await user.clear(screen.getByLabelText('Base URL'))
    await user.type(screen.getByLabelText('Base URL'), 'https://model.example/v1')
    await user.type(screen.getByLabelText('模型名称'), 'gpt-main')
    await user.type(screen.getByLabelText('API key'), 'new-secret-key')
    await user.clear(screen.getByLabelText('超时秒数'))
    await user.type(screen.getByLabelText('超时秒数'), '20')
    await user.click(screen.getByRole('button', { name: '保存模型配置' }))

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('new-secret-key'),
      }),
    )

    await user.click(screen.getByRole('button', { name: '测试连接' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles/21/test',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '设为当前' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles/21/activate',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('selects a knowledge base and scopes capture search and chat requests', async () => {
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('询问或记录')
    await user.selectOptions(screen.getByLabelText('知识库'), '2')

    await user.type(screen.getByLabelText('询问 Lumen'), '项目资料怎么引用？')
    await user.click(screen.getByRole('button', { name: '询问 Lumen' }))
    await screen.findByText('带引用的可信回答。')
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/chat/stream',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"knowledge_base_id":2'),
      }),
    )

    await user.click(screen.getByRole('button', { name: '添加资料' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/notes',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"knowledge_base_id":2'),
      }),
    )

    await user.click(screen.getByRole('button', { name: '链接' }))
    await user.type(screen.getByLabelText('网页链接'), 'https://example.com/lumen')
    await user.click(screen.getByRole('button', { name: '添加链接' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/links',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"knowledge_base_id":2'),
      }),
    )

    await user.click(screen.getByRole('button', { name: '文件' }))
    const file = new File(['Scoped upload.'], 'scoped-upload.txt', { type: 'text/plain' })
    await user.upload(screen.getByLabelText('选择资料文件'), file)
    await user.click(screen.getByRole('button', { name: '上传文件' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/uploads?knowledge_base_id=2',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '链接' }))
    await user.type(screen.getByLabelText('网页链接'), 'https://example.com/crawl')
    await user.click(screen.getByLabelText('深度抓取（递归抓取同域页面）'))
    await user.click(screen.getByRole('button', { name: '深度抓取' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/crawls',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"knowledge_base_id":2'),
      }),
    )

    await user.click(screen.getByRole('button', { name: '书签' }))
    await user.type(screen.getByLabelText('书签 HTML 内容'), '<A HREF="https://example.com/bookmark">Example</A>')
    await user.click(screen.getByRole('button', { name: '导入书签' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/bookmarks',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"knowledge_base_id":2'),
      }),
    )

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/sources?knowledge_base_id=2',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs?limit=4&knowledge_base_id=2',
      expect.objectContaining({ method: 'GET' }),
    )

    await user.click(screen.getByRole('button', { name: '搜索' }))
    await user.type(screen.getByLabelText('全局搜索'), 'link capture')
    await user.click(screen.getByRole('button', { name: '执行搜索' }))
    const globalSearchUrl = vi
      .mocked(fetch)
      .mock.calls.map(([url]) => String(url))
      .find((url) => url.includes('/api/global-search?') && url.includes('q=link+capture'))
    expect(globalSearchUrl).toContain('knowledge_base_id=2')
  })

  it('ignores pending stream chunks and final response after switching knowledge base', async () => {
    const defaultFetch = vi.mocked(fetch).getMockImplementation()
    const delayedStream = deferredStreamResponse()
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/chat/stream') && init?.method === 'POST' && String(init.body).includes('切换期间的问题')) {
        return delayedStream.response
      }
      if (!defaultFetch) throw new Error(`Unhandled request: ${url}`)
      return defaultFetch(input, init)
    })

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('询问或记录')
    await user.type(screen.getByLabelText('询问 Lumen'), '切换期间的问题')
    await user.click(screen.getByRole('button', { name: '询问 Lumen' }))
    expect(await screen.findByText('正在生成回答...')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('知识库'), '2')
    await waitFor(() => expect(screen.queryByText('正在生成回答...')).not.toBeInTheDocument())

    delayedStream.push(
      [
        'event: chunk',
        'data: {"text":"旧知识库回答"}',
        '',
        'event: final',
        'data: {"conversation_id":1,"message_id":99,"answer":"旧知识库回答","citations":[{"source_id":1,"source_title":"旧知识库资料","chunk_id":1,"quote":"旧引用","matched_terms":[],"matched_date":null,"match_reason":""}],"memories":[],"confidence":"grounded","answer_mode":"llm","fallback_reason":null}',
        '',
      ].join('\n'),
    )
    delayedStream.close()

    await waitFor(() => expect(screen.queryByText('旧知识库回答')).not.toBeInTheDocument())
    expect(screen.queryByText('旧知识库资料')).not.toBeInTheDocument()
    expect(screen.queryByText('旧引用')).not.toBeInTheDocument()
  })

  it('does not start fallback when a stale stream fails after switching knowledge base', async () => {
    const defaultFetch = vi.mocked(fetch).getMockImplementation()
    const delayedFailure = deferredRejectedResponse()
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/chat/stream') && init?.method === 'POST' && String(init.body).includes('失败后切换')) {
        return delayedFailure.response
      }
      if (!defaultFetch) throw new Error(`Unhandled request: ${url}`)
      return defaultFetch(input, init)
    })

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('询问或记录')
    await user.type(screen.getByLabelText('询问 Lumen'), '失败后切换')
    await user.click(screen.getByRole('button', { name: '询问 Lumen' }))
    expect(await screen.findByText('正在生成回答...')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('知识库'), '2')
    await waitFor(() => expect(screen.queryByText('正在生成回答...')).not.toBeInTheDocument())
    delayedFailure.reject()

    await waitFor(() => {
      const staleFallback = vi
        .mocked(fetch)
        .mock.calls.some(([url, init]) => String(url).endsWith('/api/chat') && init?.method === 'POST' && String(init.body).includes('失败后切换'))
      expect(staleFallback).toBe(false)
    })
    expect(screen.queryByText('带引用的可信回答。')).not.toBeInTheDocument()
    expect(screen.queryByText('验收笔记')).not.toBeInTheDocument()
  })

  it('saves embedding profile fields from settings', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '设置' }))
    await screen.findByText('备用模型')
    await user.click(screen.getByRole('button', { name: '编辑' }))

    expect(screen.getByLabelText('支持聊天')).toBeChecked()
    await user.click(screen.getByLabelText('支持 embedding'))
    await user.type(screen.getByLabelText('Embedding 模型'), 'text-embedding-3-small')
    await user.clear(screen.getByLabelText('Embedding 维度'))
    await user.type(screen.getByLabelText('Embedding 维度'), '1536')
    await user.click(screen.getByRole('button', { name: '保存模型配置' }))

    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles/21',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('"supports_embedding":true'),
      }),
    )
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles/21',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('"embedding_model":"text-embedding-3-small"'),
      }),
    )
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles/21',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('"embedding_dimensions":1536'),
      }),
    )

    await user.click(screen.getByRole('button', { name: '编辑' }))
    await user.click(screen.getByRole('button', { name: '测试 embedding' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/settings/provider-profiles/21/test-embedding',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('uses the streaming chat endpoint for questions', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByLabelText('询问 Lumen'), 'Lumen 应该引用什么？')
    await user.click(screen.getByRole('button', { name: '询问 Lumen' }))

    expect(await screen.findByText('带引用的可信回答。')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/chat/stream',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('supports Phase 1.5 global search filters and quality signals', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '搜索' }))
    await user.type(screen.getByLabelText('全局搜索'), 'Phase15 搜索')
    await user.click(screen.getByRole('button', { name: '执行搜索' }))

    expect(await screen.findByText('Phase15 全局搜索应该返回资料片段。')).toBeInTheDocument()
    expect(screen.getByText('记忆：preference')).toBeInTheDocument()
    expect(screen.getByText('回答 #2')).toBeInTheDocument()
    expect(screen.getByText('匹配关键词：phase15、搜索')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/global-search?'),
      expect.objectContaining({ method: 'GET' }),
    )

    await user.click(screen.getByLabelText('只看收藏'))
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('favorite=true'),
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('shows organization controls on sources memories and answers', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '资料库' }))
    expect(await screen.findByText('建议：Phase15')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '收藏资料' }))
    await user.click(screen.getByRole('button', { name: '确认 Phase15' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/favorites',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/tag-suggestions/41/confirm',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(within(screen.getByRole('navigation', { name: '主导航' })).getByRole('button', { name: '记忆' }))
    expect(await screen.findByText('建议：偏好')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '忽略 偏好' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/tag-suggestions/42/ignore',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '提问' }))
    await user.type(screen.getByLabelText('询问 Lumen'), 'Lumen 应该引用什么？')
    await user.click(screen.getByRole('button', { name: '询问 Lumen' }))
    expect(await screen.findByRole('button', { name: '收藏回答' })).toBeInTheDocument()
  })

  it('shows status view and retries failed sources', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(within(screen.getByRole('navigation', { name: '主导航' })).getByRole('button', { name: '状态' }))

    expect(await screen.findByText('系统状态')).toBeInTheDocument()
    expect(await screen.findByText('平台服务')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
    expect(screen.getByText('Elasticsearch')).toBeInTheDocument()
    expect(screen.getByText('Celery Beat')).toBeInTheDocument()
    expect(screen.getByText('索引失败：1')).toBeInTheDocument()
    expect(screen.getByText('标签建议：2')).toBeInTheDocument()
    expect(screen.getByText('失败链接')).toBeInTheDocument()
    expect(screen.getByText('摄取任务')).toBeInTheDocument()
    expect(screen.getByText('处理中')).toBeInTheDocument()
    expect(screen.getByText('phase-1-1.txt')).toBeInTheDocument()
    expect(screen.getByText('temporary link failure')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '取消任务' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/101/cancel',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '重试任务' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/ingestion-jobs/102/retry',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '重试资料' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/sources/12/retry',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('renders status view when service health payload is missing', async () => {
    const defaultFetch = vi.mocked(fetch).getMockImplementation()
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (url.endsWith('/api/status') && method === 'GET') {
        return jsonResponse({
          runtime: {
            llm_mode: 'llm',
            llm_provider: 'openai-compatible',
            llm_model: 'gpt-test',
            llm_configured: true,
            llm_fallback_enabled: true,
            embedding_mode: 'hash',
            configuration_hint: null,
            latest_fallback_reason: null,
            runtime_source: 'environment',
            active_profile_id: null,
            active_profile_name: null,
          },
          source_counts: { total: 2, indexed: 1, failed: 1, pending: 0, parsing: 0 },
          ingestion_jobs: { queued: 0, running: 1, succeeded: 0, failed: 1, canceled: 0 },
          failed_sources: [],
          pending_tag_suggestion_count: 0,
          latest_fallback_reason: null,
          suggested_actions: [],
        })
      }

      if (!defaultFetch) throw new Error(`Unhandled request: ${url}`)
      return defaultFetch(input, init)
    })

    const user = userEvent.setup()
    render(<App />)

    await user.click(within(screen.getByRole('navigation', { name: '主导航' })).getByRole('button', { name: '状态' }))

    const platformServices = await screen.findByText('平台服务')
    expect(platformServices).toBeInTheDocument()
    expect(within(platformServices.parentElement ?? document.body).getByText('0')).toBeInTheDocument()
  })

  it('supports controlled Agent configuration runs and reranker setup', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Agent' }))

    expect((await screen.findAllByText('只读研究 Agent')).length).toBeGreaterThan(0)
    expect(screen.getByText('全局搜索、记忆搜索')).toBeInTheDocument()
    expect(screen.getByText('外部 reranker · rerank-test')).toBeInTheDocument()
    expect(screen.getByText('global_search · search')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '运行 Agent' }))
    expect(await screen.findByText('我运行了 全局搜索、记忆搜索。最相关资料是「全局搜索资料」。')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/agent/runs',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.click(screen.getByRole('button', { name: '保存并启用' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/agent/profiles',
      expect.objectContaining({ method: 'POST' }),
    )

    await user.type(screen.getByLabelText('Base URL'), 'https://rerank.example/v1')
    await user.type(screen.getByLabelText('模型'), 'rerank-test')
    await user.type(screen.getByLabelText('API key'), 'reranker-secret')
    await user.click(screen.getByRole('button', { name: '保存 reranker' }))
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/agent/reranker-profiles',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('renders the graph view and shows memory relations', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: '图谱' }))
    expect(await screen.findByText('记忆图谱')).toBeInTheDocument()
    expect(screen.getByLabelText('跳转到记忆')).toBeInTheDocument()
  })
})
