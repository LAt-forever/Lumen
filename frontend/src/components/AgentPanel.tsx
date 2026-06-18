import { FormEvent, useMemo, useState } from 'react'

import {
  useActivateAgentProfile,
  useActivateRerankerProfile,
  useAgentProfiles,
  useAgentToolLogs,
  useCreateAgentProfile,
  useCreateRerankerProfile,
  useRerankerProfiles,
  useRunAgent,
} from '../api/hooks'
import type { AgentToolName } from '../api/types'

const toolOptions: Array<{ value: AgentToolName; label: string }> = [
  { value: 'global_search', label: '全局搜索' },
  { value: 'memory_search', label: '记忆搜索' },
  { value: 'memory_graph', label: '记忆图谱' },
]

export function AgentPanel() {
  const profilesQuery = useAgentProfiles()
  const logsQuery = useAgentToolLogs()
  const rerankersQuery = useRerankerProfiles()
  const createProfile = useCreateAgentProfile()
  const activateProfile = useActivateAgentProfile()
  const runAgent = useRunAgent()
  const createReranker = useCreateRerankerProfile()
  const activateReranker = useActivateRerankerProfile()

  const [message, setMessage] = useState('Phase15 搜索和记忆里有什么？')
  const [profileName, setProfileName] = useState('只读研究 Agent')
  const [instructions, setInstructions] = useState('只使用已授权的只读工具；证据不足时说明不知道。')
  const [enabledTools, setEnabledTools] = useState<AgentToolName[]>(['global_search', 'memory_search'])
  const [rerankerName, setRerankerName] = useState('外部 reranker')
  const [rerankerBaseUrl, setRerankerBaseUrl] = useState('')
  const [rerankerModel, setRerankerModel] = useState('')
  const [rerankerKey, setRerankerKey] = useState('')

  const profiles = profilesQuery.data ?? []
  const activeProfile = profiles.find((profile) => profile.is_active)
  const logs = logsQuery.data ?? []
  const rerankers = rerankersQuery.data ?? []
  const activeReranker = rerankers.find((profile) => profile.is_active)
  const isBusy = createProfile.isPending || activateProfile.isPending || runAgent.isPending

  const toolSummary = useMemo(() => {
    if (!activeProfile) return '尚未启用 Agent 配置'
    return activeProfile.enabled_tools.map((tool) => toolOptions.find((option) => option.value === tool)?.label ?? tool).join('、')
  }, [activeProfile])

  const toggleTool = (tool: AgentToolName) => {
    setEnabledTools((current) => (current.includes(tool) ? current.filter((item) => item !== tool) : [...current, tool]))
  }

  const submitProfile = (event: FormEvent) => {
    event.preventDefault()
    createProfile.mutate({
      name: profileName.trim(),
      instructions: instructions.trim(),
      enabled_tools: enabledTools,
      require_approval: true,
      is_active: true,
    })
  }

  const submitReranker = (event: FormEvent) => {
    event.preventDefault()
    createReranker.mutate({
      name: rerankerName.trim(),
      provider: 'openai-compatible',
      base_url: rerankerBaseUrl.trim() || null,
      model: rerankerModel.trim() || null,
      api_key: rerankerKey.trim() || null,
      top_n: 20,
      is_active: true,
    })
  }

  return (
    <section className="center-panel full-span" aria-label="Agent">
      <div className="panel-header">
        <div>
          <p className="eyebrow">可控工具</p>
          <h2>Agent</h2>
        </div>
        <span className="mode-pill">{activeProfile ? '已配置' : '待配置'}</span>
      </div>

      <div className="settings-grid">
        <div className="settings-section">
          <h3>运行一次</h3>
          <form
            className="form-stack"
            onSubmit={(event) => {
              event.preventDefault()
              runAgent.mutate(message)
            }}
          >
            <label className="field-label" htmlFor="agent-message">
              任务
            </label>
            <textarea id="agent-message" rows={4} value={message} onChange={(event) => setMessage(event.target.value)} />
            <button disabled={isBusy || !message.trim()} type="submit">
              运行 Agent
            </button>
          </form>

          {runAgent.data ? (
            <div className="agent-answer">
              <strong>Agent 回答</strong>
              <p>{runAgent.data.answer}</p>
              <div className="tag-row">
                {runAgent.data.used_tools.map((tool) => (
                  <span className="mode-pill" key={tool}>
                    {toolOptions.find((option) => option.value === tool)?.label ?? tool}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="settings-section">
          <h3>当前权限</h3>
          <div className="stack-list">
            <article className="list-row">
              <strong>{activeProfile?.name ?? '未启用配置'}</strong>
              <p>{toolSummary}</p>
            </article>
            <article className="list-row">
              <strong>审批策略</strong>
              <p>{activeProfile?.require_approval ? '写入类工具需要审批；当前仅启用只读工具。' : '不要求审批'}</p>
            </article>
            <article className="list-row">
              <strong>Reranker</strong>
              <p>{activeReranker ? `${activeReranker.name} · ${activeReranker.model ?? '未指定模型'}` : '未启用外部 reranker'}</p>
            </article>
          </div>
        </div>

        <div className="settings-section">
          <h3>Agent 配置</h3>
          <form className="form-stack" onSubmit={submitProfile}>
            <label className="field-label" htmlFor="agent-profile-name">
              配置名称
            </label>
            <input id="agent-profile-name" value={profileName} onChange={(event) => setProfileName(event.target.value)} />
            <label className="field-label" htmlFor="agent-instructions">
              行为指令
            </label>
            <textarea id="agent-instructions" rows={3} value={instructions} onChange={(event) => setInstructions(event.target.value)} />
            <div className="agent-tool-grid" aria-label="工具权限">
              {toolOptions.map((option) => (
                <label key={option.value}>
                  <input checked={enabledTools.includes(option.value)} onChange={() => toggleTool(option.value)} type="checkbox" />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
            <button disabled={!profileName.trim() || enabledTools.length === 0 || createProfile.isPending} type="submit">
              保存并启用
            </button>
          </form>
          <div className="stack-list">
            {profiles.map((profile) => (
              <article className="list-row" key={profile.id}>
                <strong>{profile.name}</strong>
                <p>{profile.enabled_tools.join(' / ')}</p>
                <button disabled={profile.is_active} onClick={() => activateProfile.mutate(profile.id)} type="button">
                  {profile.is_active ? '当前配置' : '设为当前'}
                </button>
              </article>
            ))}
          </div>
        </div>

        <div className="settings-section">
          <h3>Reranker 配置</h3>
          <form className="form-stack" onSubmit={submitReranker}>
            <label className="field-label" htmlFor="reranker-name">
              配置名称
            </label>
            <input id="reranker-name" value={rerankerName} onChange={(event) => setRerankerName(event.target.value)} />
            <label className="field-label" htmlFor="reranker-base-url">
              Base URL
            </label>
            <input id="reranker-base-url" value={rerankerBaseUrl} onChange={(event) => setRerankerBaseUrl(event.target.value)} />
            <label className="field-label" htmlFor="reranker-model">
              模型
            </label>
            <input id="reranker-model" value={rerankerModel} onChange={(event) => setRerankerModel(event.target.value)} />
            <label className="field-label" htmlFor="reranker-api-key">
              API key
            </label>
            <input id="reranker-api-key" value={rerankerKey} onChange={(event) => setRerankerKey(event.target.value)} type="password" />
            <button disabled={!rerankerName.trim() || createReranker.isPending} type="submit">
              保存 reranker
            </button>
          </form>
          <div className="stack-list">
            {rerankers.map((profile) => (
              <article className="list-row" key={profile.id}>
                <strong>{profile.name}</strong>
                <p>
                  {profile.provider} · {profile.model ?? '未指定模型'} · {profile.api_key_configured ? '密钥已配置' : '无密钥'}
                </p>
                <button disabled={profile.is_active} onClick={() => activateReranker.mutate(profile.id)} type="button">
                  {profile.is_active ? '当前 reranker' : '设为当前'}
                </button>
              </article>
            ))}
          </div>
        </div>

        <div className="settings-section full-width-section">
          <h3>工具日志</h3>
          <div className="stack-list results-list">
            {logs.map((log) => (
              <article className="list-row" key={log.id}>
                <strong>
                  {log.tool_name} · {log.action}
                </strong>
                <p>{log.result_summary ?? log.error_message ?? '无摘要'}</p>
                <span className="mode-pill">{log.status}</span>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
