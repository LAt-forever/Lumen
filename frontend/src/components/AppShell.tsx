import { useState } from 'react'
import type { LucideIcon } from 'lucide-react'

import type { ChatResponse } from '../api/types'
import { CapturePanel } from './CapturePanel'
import { ChatPanel } from './ChatPanel'
import { ContextPanel } from './ContextPanel'
import { MemoryManager } from './MemoryManager'
import { MemoryInbox } from './MemoryInbox'
import { ReviewPanel } from './ReviewPanel'
import { SearchPanel } from './SearchPanel'
import { SettingsPanel } from './SettingsPanel'
import { SourceList } from './SourceList'

export type ViewKey = 'today' | 'ask' | 'library' | 'memory' | 'search' | 'review' | 'settings'

export type NavItem = {
  label: string
  icon: LucideIcon
  view: ViewKey
}

type AppShellProps = {
  navItems: NavItem[]
}

export function AppShell({ navItems }: AppShellProps) {
  const [lastResponse, setLastResponse] = useState<ChatResponse>()
  const [activeView, setActiveView] = useState<ViewKey>('today')
  const activeItem = navItems.find((item) => item.view === activeView) ?? navItems[0]

  const renderCenter = () => {
    if (activeView === 'today') {
      return (
        <>
          <CapturePanel onResponse={setLastResponse} />
          {lastResponse ? <ChatPanel response={lastResponse} /> : null}
          <SourceList />
          <ReviewPanel />
        </>
      )
    }
    if (activeView === 'ask') {
      return (
        <>
          <CapturePanel onResponse={setLastResponse} />
          <ChatPanel response={lastResponse} />
        </>
      )
    }
    if (activeView === 'library') {
      return (
        <>
          <CapturePanel onResponse={setLastResponse} />
          <SourceList />
        </>
      )
    }
    if (activeView === 'memory') {
      return (
        <>
          <MemoryManager />
          <MemoryInbox />
        </>
      )
    }
    if (activeView === 'search') {
      return <SearchPanel />
    }
    if (activeView === 'review') {
      return <ReviewPanel />
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
      </aside>

      <main className={`workbench${activeView === 'today' || activeView === 'ask' || activeView === 'library' ? '' : ' single-pane'}`}>
        <header className="top-bar">
          <div>
            <p className="eyebrow">从上次停下的地方继续</p>
            <h1>{activeItem?.label === '今天' ? '询问、记录，并信任 Lumen 记住的内容。' : activeItem?.label}</h1>
          </div>
          <div className="system-state" aria-label="Lumen 状态">
            <span>本地优先</span>
            <span>摘录模式</span>
          </div>
        </header>

        <section className="center-column">
          {renderCenter()}
        </section>

        {activeView === 'today' || activeView === 'ask' || activeView === 'library' ? (
          <aside className="context-column">
            <MemoryInbox />
            <ContextPanel response={lastResponse} />
          </aside>
        ) : null}
      </main>
    </div>
  )
}
