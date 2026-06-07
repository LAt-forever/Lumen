const confidenceLabels: Record<string, string> = {
  grounded: '有资料支撑',
  'memory-only': '仅来自记忆',
  weak: '证据不足',
}

const memoryTypeLabels: Record<string, string> = {
  preference: '偏好',
  fact: '事实',
  project: '项目',
  relationship: '关系',
  goal: '目标',
  event: '事件',
  note: '笔记',
}

const sourceStatusLabels: Record<string, string> = {
  pending: '待处理',
  parsing: '解析中',
  indexed: '已索引',
  failed: '解析失败',
}

const suggestedActionLabels: Record<string, string> = {
  'Add a source to begin.': '添加一条资料开始使用。',
  'Confirm a memory so Lumen can personalize future answers.': '确认一条记忆，让 Lumen 在后续回答中更贴合你。',
  'Ask Lumen a follow-up question using your confirmed memories.': '基于已确认的记忆继续追问 Lumen。',
}

export function formatConfidence(value: string) {
  return confidenceLabels[value] ?? value
}

export function formatMemoryType(value: string) {
  return memoryTypeLabels[value] ?? value
}

export function formatSourceStatus(value: string) {
  return sourceStatusLabels[value] ?? value
}

export function formatSuggestedAction(value: string) {
  const pendingMatch = value.match(/^Review (\d+) pending memory candidate\(s\)\.$/)
  if (pendingMatch) {
    return `处理 ${pendingMatch[1]} 条待确认记忆。`
  }
  return suggestedActionLabels[value] ?? value
}
