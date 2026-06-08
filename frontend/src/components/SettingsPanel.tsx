import { FormEvent, useState } from 'react'

import { API_BASE } from '../api/client'
import {
  useActivateProviderProfile,
  useCreateProviderProfile,
  useDeleteProviderProfile,
  useProviderProfiles,
  useRuntimeSettings,
  useTestProviderProfile,
  useUpdateProviderProfile,
} from '../api/hooks'
import type { LLMProviderProfileRead, LLMProviderProfileUpdate } from '../api/types'

type ProfileFormState = {
  name: string
  provider: string
  base_url: string
  model: string
  api_key: string
  timeout_seconds: string
  fallback_enabled: boolean
  is_active: boolean
  clear_api_key: boolean
}

const emptyProfileForm: ProfileFormState = {
  name: '',
  provider: 'openai-compatible',
  base_url: 'https://api.openai.com/v1',
  model: '',
  api_key: '',
  timeout_seconds: '30',
  fallback_enabled: true,
  is_active: false,
  clear_api_key: false,
}

function profileStatusLabel(status: LLMProviderProfileRead['status']) {
  if (status === 'ready') return '连接正常'
  if (status === 'failed') return '连接失败'
  return '未测试'
}

export function SettingsPanel() {
  const runtimeSettings = useRuntimeSettings()
  const providerProfiles = useProviderProfiles()
  const createProfile = useCreateProviderProfile()
  const updateProfile = useUpdateProviderProfile()
  const activateProfile = useActivateProviderProfile()
  const testProfile = useTestProviderProfile()
  const deleteProfile = useDeleteProviderProfile()
  const [editingProfileId, setEditingProfileId] = useState<number | null>(null)
  const [form, setForm] = useState<ProfileFormState>(emptyProfileForm)

  const settings = runtimeSettings.data
  const profiles = providerProfiles.data ?? []
  const answerMode = settings?.llm_mode === 'llm' ? 'LLM 模式' : '摘录模式'
  const modelName = settings?.llm_model ?? '未配置'
  const keyStatus = settings?.llm_configured ? 'API key 已配置' : 'API key 未配置'
  const fallbackStatus = settings?.llm_fallback_enabled ? '启用失败回退' : '未启用失败回退'
  const runtimeSource =
    settings?.runtime_source === 'database-profile'
      ? `SQLite profile${settings.active_profile_name ? ` · ${settings.active_profile_name}` : ''}`
      : '环境变量'
  const isMutating =
    createProfile.isPending ||
    updateProfile.isPending ||
    activateProfile.isPending ||
    testProfile.isPending ||
    deleteProfile.isPending
  const canSubmit =
    Boolean(form.name.trim()) && Boolean(form.base_url.trim()) && Boolean(form.model.trim()) && Number(form.timeout_seconds) > 0

  const resetForm = () => {
    setEditingProfileId(null)
    setForm(emptyProfileForm)
  }

  const updateForm = <TKey extends keyof ProfileFormState>(field: TKey, value: ProfileFormState[TKey]) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const startEdit = (profile: LLMProviderProfileRead) => {
    setEditingProfileId(profile.id)
    setForm({
      name: profile.name,
      provider: profile.provider,
      base_url: profile.base_url,
      model: profile.model,
      api_key: '',
      timeout_seconds: String(profile.timeout_seconds),
      fallback_enabled: profile.fallback_enabled,
      is_active: profile.is_active,
      clear_api_key: false,
    })
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return

    const basePayload = {
      name: form.name.trim(),
      provider: form.provider.trim(),
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      timeout_seconds: Number(form.timeout_seconds),
      fallback_enabled: form.fallback_enabled,
      is_active: form.is_active,
    }
    const apiKey = form.api_key.trim()

    if (editingProfileId !== null) {
      const payload: LLMProviderProfileUpdate = {
        ...basePayload,
        clear_api_key: form.clear_api_key,
      }
      if (apiKey) {
        payload.api_key = apiKey
      }
      updateProfile.mutate({ profileId: editingProfileId, payload }, { onSuccess: resetForm })
      return
    }

    createProfile.mutate(
      {
        ...basePayload,
        api_key: apiKey || null,
      },
      { onSuccess: resetForm },
    )
  }

  const handleDelete = (profile: LLMProviderProfileRead) => {
    if (window.confirm(`删除模型配置「${profile.name}」？`)) {
      deleteProfile.mutate(profile.id)
    }
  }

  return (
    <section className="center-panel full-span" aria-label="设置">
      <div className="panel-header">
        <div>
          <p className="eyebrow">本地运行</p>
          <h2>设置</h2>
        </div>
      </div>

      <div className="settings-grid">
        <div className="settings-section">
          <h3>运行状态</h3>
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
              <strong>运行来源</strong>
              <p>{runtimeSource}</p>
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
            {settings?.configuration_hint ? (
              <article className="list-row">
                <strong>配置提示</strong>
                <p>{settings.configuration_hint}</p>
              </article>
            ) : null}
            {settings?.latest_fallback_reason ? (
              <article className="list-row">
                <strong>最近回退</strong>
                <p>{settings.latest_fallback_reason}</p>
              </article>
            ) : null}
            <article className="list-row">
              <strong>数据策略</strong>
              <p>模型密钥存入本机 SQLite；API 不会读回明文。</p>
            </article>
          </div>
        </div>

        <div className="settings-section">
          <h3>{editingProfileId === null ? '模型配置' : '编辑模型配置'}</h3>
          <form className="form-stack" onSubmit={handleSubmit}>
            <label className="field-label" htmlFor="provider-profile-name">
              配置名称
            </label>
            <input
              id="provider-profile-name"
              onChange={(event) => updateForm('name', event.target.value)}
              value={form.name}
            />

            <label className="field-label" htmlFor="provider-profile-provider">
              模型提供方
            </label>
            <input
              id="provider-profile-provider"
              onChange={(event) => updateForm('provider', event.target.value)}
              value={form.provider}
            />

            <label className="field-label" htmlFor="provider-profile-base-url">
              Base URL
            </label>
            <input
              id="provider-profile-base-url"
              onChange={(event) => updateForm('base_url', event.target.value)}
              type="url"
              value={form.base_url}
            />

            <div className="inline-fields">
              <div>
                <label className="field-label" htmlFor="provider-profile-model">
                  模型名称
                </label>
                <input
                  id="provider-profile-model"
                  onChange={(event) => updateForm('model', event.target.value)}
                  value={form.model}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="provider-profile-timeout">
                  超时秒数
                </label>
                <input
                  id="provider-profile-timeout"
                  min="1"
                  onChange={(event) => updateForm('timeout_seconds', event.target.value)}
                  type="number"
                  value={form.timeout_seconds}
                />
              </div>
            </div>

            <label className="field-label" htmlFor="provider-profile-api-key">
              API key
            </label>
            <input
              autoComplete="off"
              id="provider-profile-api-key"
              onChange={(event) => updateForm('api_key', event.target.value)}
              type="password"
              value={form.api_key}
            />

            {editingProfileId !== null ? (
              <label className="checkbox-row">
                <input
                  checked={form.clear_api_key}
                  onChange={(event) => updateForm('clear_api_key', event.target.checked)}
                  type="checkbox"
                />
                清除已保存密钥
              </label>
            ) : null}

            <label className="checkbox-row">
              <input
                checked={form.fallback_enabled}
                onChange={(event) => updateForm('fallback_enabled', event.target.checked)}
                type="checkbox"
              />
              启用失败回退
            </label>
            <label className="checkbox-row">
              <input checked={form.is_active} onChange={(event) => updateForm('is_active', event.target.checked)} type="checkbox" />
              保存后设为当前
            </label>

            <div className="action-row">
              <button disabled={isMutating || !canSubmit} type="submit">
                保存模型配置
              </button>
              {editingProfileId !== null ? (
                <button className="secondary" onClick={resetForm} type="button">
                  取消编辑
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </div>

      <div className="profile-list" aria-label="模型配置列表">
        {providerProfiles.isLoading ? <p>正在读取模型配置...</p> : null}
        {profiles.length === 0 && !providerProfiles.isLoading ? <p>还没有模型配置。</p> : null}
        {profiles.map((profile) => (
          <article className="profile-row" key={profile.id}>
            <div>
              <div className="profile-title-row">
                <h3>{profile.name}</h3>
                <span className="mode-pill">{profile.is_active ? '当前使用' : '未启用'}</span>
                <span className="mode-pill">{profileStatusLabel(profile.status)}</span>
              </div>
              <p>{profile.model}</p>
              <p>{profile.base_url}</p>
              <p>密钥：{profile.api_key_configured ? '已保存' : '未保存'}</p>
              {profile.last_error ? <p>最近错误：{profile.last_error}</p> : null}
            </div>
            <div className="memory-actions">
              <button className="secondary" onClick={() => startEdit(profile)} type="button">
                编辑
              </button>
              <button className="secondary" disabled={isMutating} onClick={() => testProfile.mutate(profile.id)} type="button">
                测试连接
              </button>
              {!profile.is_active ? (
                <button disabled={isMutating} onClick={() => activateProfile.mutate(profile.id)} type="button">
                  设为当前
                </button>
              ) : null}
              {!profile.is_active ? (
                <button className="secondary danger" disabled={isMutating} onClick={() => handleDelete(profile)} type="button">
                  删除
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
