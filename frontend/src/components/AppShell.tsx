import { useEffect, useRef, useState } from 'react'
import { LogOut } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { useRuntimeSettings } from '../api/hooks'
import type { ChatResponse } from '../api/types'
import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'
import { AgentPanel } from './AgentPanel'
import { CapturePanel } from './CapturePanel'
import { ChatPanel } from './ChatPanel'
import { ContextPanel } from './ContextPanel'
import { IngestionProgressPanel } from './IngestionProgressPanel'
import { KnowledgeBasePanel } from './KnowledgeBasePanel'
import { KnowledgeBaseSelector } from './KnowledgeBaseSelector'
import { MemoryGraphPanel } from './MemoryGraphPanel'
import { MemoryManager } from './MemoryManager'
import { MemoryInbox } from './MemoryInbox'
import { ReviewPanel } from './ReviewPanel'
import { SearchPanel } from './SearchPanel'
import { SettingsPanel } from './SettingsPanel'
import { SourceList } from './SourceList'
import { StatusPanel } from './StatusPanel'

export type ViewKey =
  | 'today'
  | 'ask'
  | 'library'
  | 'knowledge-base'
  | 'memory'
  | 'graph'
  | 'agent'
  | 'search'
  | 'review'
  | 'status'
  | 'settings'

export type NavItem = {
  label: string
  icon: LucideIcon
  view: ViewKey
}

type AppShellProps = {
  navItems: NavItem[]
  accountLabel?: string
  onLogout?: () => void
}

export function AppShell({ accountLabel, navItems, onLogout }: AppShellProps) {
  const [lastResponse, setLastResponse] = useState<ChatResponse>()
  const [streamingAnswer, setStreamingAnswer] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeView, setActiveView] = useState<ViewKey>('today')
  const { activeKnowledgeBaseId } = useKnowledgeBaseContext()
  const previousKnowledgeBaseId = useRef<number | null>(activeKnowledgeBaseId)
  const activeKnowledgeBaseIdRef = useRef<number | null>(activeKnowledgeBaseId)
  const requestGenerationRef = useRef(0)
  const activeItem = navItems.find((item) => item.view === activeView) ?? navItems[0]
  const runtimeSettings = useRuntimeSettings()
  const answerModeLabel = runtimeSettings.data?.llm_mode === 'llm' ? 'LLM 模式' : '摘录模式'

  useEffect(() => {
    activeKnowledgeBaseIdRef.current = activeKnowledgeBaseId
    if (previousKnowledgeBaseId.current === activeKnowledgeBaseId) return
    previousKnowledgeBaseId.current = activeKnowledgeBaseId
    requestGenerationRef.current += 1
    setLastResponse(undefined)
    setStreamingAnswer('')
    setIsStreaming(false)
  }, [activeKnowledgeBaseId])

  const isCurrentRequest = (knowledgeBaseId: number | null, requestId: number) =>
    activeKnowledgeBaseIdRef.current === knowledgeBaseId && requestGenerationRef.current === requestId

  const handleResponse = (response: ChatResponse, knowledgeBaseId: number | null, requestId: number) => {
    if (!isCurrentRequest(knowledgeBaseId, requestId)) return
    setLastResponse(response)
    setStreamingAnswer('')
    setIsStreaming(false)
  }

  const handleStreamStart = (knowledgeBaseId: number | null) => {
    if (activeKnowledgeBaseIdRef.current !== knowledgeBaseId) {
      return null
    }
    requestGenerationRef.current += 1
    const requestId = requestGenerationRef.current
    setLastResponse(undefined)
    setStreamingAnswer('')
    setIsStreaming(true)
    return requestId
  }

  const handleStreamChunk = (text: string, knowledgeBaseId: number | null, requestId: number) => {
    if (!isCurrentRequest(knowledgeBaseId, requestId)) return
    setStreamingAnswer((current) => `${current}${text}`)
  }

  const capturePanel = (
    <CapturePanel onResponse={handleResponse} onStreamChunk={handleStreamChunk} onStreamStart={handleStreamStart} />
  )
  const chatPanel = <ChatPanel isStreaming={isStreaming} response={lastResponse} streamingAnswer={streamingAnswer} />

  const renderCenter = () => {
    if (activeView === 'today') {
      return (
        <>
          {capturePanel}
          {lastResponse || isStreaming ? chatPanel : null}
          <SourceList />
          <ReviewPanel />
        </>
      )
    }
    if (activeView === 'ask') {
      return (
        <>
          {capturePanel}
          {chatPanel}
        </>
      )
    }
    if (activeView === 'library') {
      return (
        <>
          {capturePanel}
          <SourceList />
        </>
      )
    }
    if (activeView === 'knowledge-base') {
      return <KnowledgeBasePanel />
    }
    if (activeView === 'memory') {
      return (
        <>
          <MemoryManager />
          <MemoryInbox />
        </>
      )
    }
    if (activeView === 'graph') {
      return <MemoryGraphPanel />
    }
    if (activeView === 'agent') {
      return <AgentPanel />
    }
    if (activeView === 'search') {
      return <SearchPanel />
    }
    if (activeView === 'review') {
      return <ReviewPanel />
    }
    if (activeView === 'status') {
      return <StatusPanel />
    }
    return <SettingsPanel />
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span>Lumen</span>
        </div>
        <nav className="nav-list" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button
                aria-current={activeView === item.view ? 'page' : undefined}
                className={`nav-item${activeView === item.view ? ' active' : ''}`}
                key={item.label}
                onClick={() => setActiveView(item.view)}
                type="button"
              >
                <Icon size={18} strokeWidth={1.9} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
        {accountLabel && onLogout ? (
          <div className="sidebar-account">
            <span>{accountLabel}</span>
            <button aria-label="退出登录" className="icon-text-button" onClick={onLogout} type="button">
              <LogOut size={16} strokeWidth={1.9} aria-hidden="true" />
              <span>退出</span>
            </button>
          </div>
        ) : null}
      </aside>

      <main className={`workbench${activeView === 'today' || activeView === 'ask' || activeView === 'library' ? '' : ' single-pane'}`}>
        <header className="top-bar">
          <div>
            <p className="eyebrow">从上次停下的地方继续</p>
            <h1>{activeItem?.label === '今天' ? '询问、记录，并信任 Lumen 记住的内容。' : activeItem?.label}</h1>
          </div>
          <div className="top-workflow">
            <KnowledgeBaseSelector onManage={() => setActiveView('knowledge-base')} />
            <div className="system-state" aria-label="Lumen 状态">
              <span>本地优先</span>
              <span>{answerModeLabel}</span>
            </div>
          </div>
        </header>

        <section className="center-column">
          {renderCenter()}
        </section>

        {activeView === 'today' || activeView === 'ask' || activeView === 'library' ? (
          <aside className="context-column">
            <IngestionProgressPanel mode="compact" onOpenStatus={() => setActiveView('status')} />
            <MemoryInbox />
            <ContextPanel response={lastResponse} />
          </aside>
        ) : null}
      </main>
    </div>
  )
}
