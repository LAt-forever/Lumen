import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Activity, BookOpen, Brain, Home, MessageSquare, Search, Settings, Sparkles } from 'lucide-react'

import { AppShell } from './components/AppShell'
import type { NavItem } from './components/AppShell'

const queryClient = new QueryClient()

const navItems: NavItem[] = [
  { label: '今天', icon: Home, view: 'today' },
  { label: '提问', icon: MessageSquare, view: 'ask' },
  { label: '资料库', icon: BookOpen, view: 'library' },
  { label: '记忆', icon: Brain, view: 'memory' },
  { label: '搜索', icon: Search, view: 'search' },
  { label: '回顾', icon: Sparkles, view: 'review' },
  { label: '状态', icon: Activity, view: 'status' },
  { label: '设置', icon: Settings, view: 'settings' },
]

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell navItems={navItems} />
    </QueryClientProvider>
  )
}
