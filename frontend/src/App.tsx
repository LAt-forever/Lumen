import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Activity, Bot, BookOpen, Brain, Database, GitBranch, Home, Images, MessageSquare, Search, Settings, Sparkles } from 'lucide-react'

import { AuthProvider, useAuth } from './auth/AuthContext'
import { AppShell } from './components/AppShell'
import { LoginPage } from './components/LoginPage'
import { KnowledgeBaseProvider } from './knowledgeBase/KnowledgeBaseContext'
import type { NavItem } from './components/AppShell'

const queryClient = new QueryClient()

const navItems: NavItem[] = [
  { label: '今天', icon: Home, view: 'today' },
  { label: '提问', icon: MessageSquare, view: 'ask' },
  { label: '资料库', icon: BookOpen, view: 'library' },
  { label: '图片库', icon: Images, view: 'images' },
  { label: '知识库', icon: Database, view: 'knowledge-base' },
  { label: '记忆', icon: Brain, view: 'memory' },
  { label: '图谱', icon: GitBranch, view: 'graph' },
  { label: 'Agent', icon: Bot, view: 'agent' },
  { label: '搜索', icon: Search, view: 'search' },
  { label: '回顾', icon: Sparkles, view: 'review' },
  { label: '状态', icon: Activity, view: 'status' },
  { label: '设置', icon: Settings, view: 'settings' },
]

function ProtectedWorkbench() {
  const { user, isChecking, logout } = useAuth()
  if (!user) {
    return <LoginPage />
  }
  return (
    <KnowledgeBaseProvider>
      <AppShell accountLabel={isChecking ? '正在验证账户' : user.email} navItems={navItems} onLogout={logout} />
    </KnowledgeBaseProvider>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ProtectedWorkbench />
      </AuthProvider>
    </QueryClientProvider>
  )
}
