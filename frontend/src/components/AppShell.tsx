import { useState } from 'react'
import type { LucideIcon } from 'lucide-react'

import type { ChatResponse } from '../api/types'
import { CapturePanel } from './CapturePanel'
import { ChatPanel } from './ChatPanel'
import { ContextPanel } from './ContextPanel'
import { MemoryInbox } from './MemoryInbox'
import { ReviewPanel } from './ReviewPanel'
import { SourceList } from './SourceList'

type NavItem = {
  label: string
  icon: LucideIcon
}

type AppShellProps = {
  navItems: NavItem[]
}

export function AppShell({ navItems }: AppShellProps) {
  const [lastResponse, setLastResponse] = useState<ChatResponse>()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span>Lumen</span>
        </div>
        <nav className="nav-list" aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button className="nav-item" key={item.label} type="button">
                <Icon size={18} strokeWidth={1.9} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </aside>

      <main className="workbench">
        <header className="top-bar">
          <div>
            <p className="eyebrow">Continue where you left off</p>
            <h1>Ask, capture, and trust what Lumen remembers.</h1>
          </div>
          <div className="system-state" aria-label="Lumen status">
            <span>Local-first</span>
            <span>Extractive mode</span>
          </div>
        </header>

        <section className="center-column">
          <CapturePanel onResponse={setLastResponse} />
          {lastResponse ? <ChatPanel response={lastResponse} /> : null}
          <SourceList />
          <ReviewPanel />
        </section>

        <aside className="context-column">
          <MemoryInbox />
          <ContextPanel response={lastResponse} />
        </aside>
      </main>
    </div>
  )
}
