import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BookOpen, Brain, Home, MessageSquare, Search, Settings, Sparkles } from 'lucide-react'

import { AppShell } from './components/AppShell'

const queryClient = new QueryClient()

const navItems = [
  { label: 'Today', icon: Home },
  { label: 'Ask', icon: MessageSquare },
  { label: 'Library', icon: BookOpen },
  { label: 'Memory', icon: Brain },
  { label: 'Search', icon: Search },
  { label: 'Review', icon: Sparkles },
  { label: 'Settings', icon: Settings },
]

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell navItems={navItems} />
    </QueryClientProvider>
  )
}
