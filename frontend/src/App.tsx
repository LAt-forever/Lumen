import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BookOpen, Brain, Home, MessageSquare, Search, Settings, Sparkles } from 'lucide-react'

import { AppShell } from './components/AppShell'

const queryClient = new QueryClient()

const navItems = [
  { label: '今天', icon: Home },
  { label: '提问', icon: MessageSquare },
  { label: '资料库', icon: BookOpen },
  { label: '记忆', icon: Brain },
  { label: '搜索', icon: Search },
  { label: '回顾', icon: Sparkles },
  { label: '设置', icon: Settings },
]

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell navItems={navItems} />
    </QueryClientProvider>
  )
}
