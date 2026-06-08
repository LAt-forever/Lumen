import { API_BASE } from '../api/client'
import { useRuntimeSettings } from '../api/hooks'

export function SettingsPanel() {
  const runtimeSettings = useRuntimeSettings()
  const settings = runtimeSettings.data
  const answerMode = settings?.llm_mode === 'llm' ? 'LLM 模式' : '摘录模式'
  const modelName = settings?.llm_model ?? '未配置'
  const keyStatus = settings?.llm_configured ? 'API key 已配置' : 'API key 未配置'
  const fallbackStatus = settings?.llm_fallback_enabled ? '启用失败回退' : '未启用失败回退'

  return (
    <section className="center-panel full-span" aria-label="设置">
      <div className="panel-header">
        <div>
          <p className="eyebrow">本地运行</p>
          <h2>设置</h2>
        </div>
      </div>
      <div className="stack-list">
        <article className="list-row">
          <strong>API 地址</strong>
          <p>{API_BASE}</p>
        </article>
        <article className="list-row">
          <strong>回答模式</strong>
          <p>{runtimeSettings.isLoading ? '正在读取运行配置...' : answerMode}</p>
        </article>
        <article className="list-row">
          <strong>模型提供方</strong>
          <p>{settings?.llm_provider ?? 'openai-compatible'}</p>
        </article>
        <article className="list-row">
          <strong>模型</strong>
          <p>{modelName}</p>
        </article>
        <article className="list-row">
          <strong>密钥状态</strong>
          <p>{keyStatus}</p>
        </article>
        <article className="list-row">
          <strong>失败策略</strong>
          <p>{fallbackStatus}</p>
        </article>
        <article className="list-row">
          <strong>数据策略</strong>
          <p>模型密钥只从本地环境变量读取，不会写入数据库。</p>
        </article>
      </div>
    </section>
  )
}
