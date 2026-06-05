import type { LucideIcon } from 'lucide-react'

type NavItem = {
  label: string
  icon: LucideIcon
}

type AppShellProps = {
  navItems: NavItem[]
}

export function AppShell({ navItems }: AppShellProps) {
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

        <section className="center-panel" aria-label="Ask or capture">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Primary workspace</p>
              <h2>Ask or capture</h2>
            </div>
            <span className="mode-pill">Ready</span>
          </div>
          <label className="field-label" htmlFor="ask-lumen">
            Ask a question, write a note, or paste a link
          </label>
          <textarea
            id="ask-lumen"
            aria-label="Ask Lumen"
            placeholder="What should I remember from this source?"
          />
          <div className="action-row">
            <button type="button">Ask Lumen</button>
            <button type="button" className="secondary">
              Add source
            </button>
          </div>
        </section>

        <aside className="context-column">
          <section className="side-panel">
            <div className="panel-header">
              <h2>Memory Inbox</h2>
              <span className="count-pill">0</span>
            </div>
            <p>No pending memories yet.</p>
          </section>
          <section className="side-panel">
            <h2>Context Now</h2>
            <p>Sources and recalled memories will appear here.</p>
          </section>
        </aside>
      </main>
    </div>
  )
}
