import { FormEvent, useState } from 'react'

import {
  useArchiveKnowledgeBase,
  useCreateKnowledgeBase,
  useDeleteKnowledgeBase,
  useRestoreKnowledgeBase,
  useUpdateKnowledgeBase,
} from '../api/hooks'
import type { KnowledgeBaseRead } from '../api/types'
import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'

type KnowledgeBaseForm = {
  name: string
  description: string
}

const emptyForm: KnowledgeBaseForm = {
  name: '',
  description: '',
}

function formFromKnowledgeBase(knowledgeBase: KnowledgeBaseRead): KnowledgeBaseForm {
  return {
    name: knowledgeBase.name,
    description: knowledgeBase.description ?? '',
  }
}

export function KnowledgeBasePanel() {
  const { activeKnowledgeBaseId, activeKnowledgeBases, archivedKnowledgeBases, setActiveKnowledgeBaseId } = useKnowledgeBaseContext()
  const createKnowledgeBase = useCreateKnowledgeBase()
  const updateKnowledgeBase = useUpdateKnowledgeBase()
  const archiveKnowledgeBase = useArchiveKnowledgeBase()
  const restoreKnowledgeBase = useRestoreKnowledgeBase()
  const deleteKnowledgeBase = useDeleteKnowledgeBase()
  const [createForm, setCreateForm] = useState<KnowledgeBaseForm>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<KnowledgeBaseForm>(emptyForm)
  const isMutating =
    createKnowledgeBase.isPending ||
    updateKnowledgeBase.isPending ||
    archiveKnowledgeBase.isPending ||
    restoreKnowledgeBase.isPending ||
    deleteKnowledgeBase.isPending

  const handleCreate = (event: FormEvent) => {
    event.preventDefault()
    const name = createForm.name.trim()
    if (!name) return
    createKnowledgeBase.mutate(
      { name, description: createForm.description.trim() || null },
      {
        onSuccess: (knowledgeBase) => {
          setCreateForm(emptyForm)
          if (knowledgeBase?.status === 'active') {
            setActiveKnowledgeBaseId(knowledgeBase.id)
          }
        },
      },
    )
  }

  const startEdit = (knowledgeBase: KnowledgeBaseRead) => {
    setEditingId(knowledgeBase.id)
    setEditForm(formFromKnowledgeBase(knowledgeBase))
  }

  const handleUpdate = (knowledgeBaseId: number) => {
    const name = editForm.name.trim()
    if (!name) return
    updateKnowledgeBase.mutate(
      {
        knowledgeBaseId,
        payload: {
          name,
          description: editForm.description.trim() || null,
        },
      },
      { onSuccess: () => setEditingId(null) },
    )
  }

  const handleArchive = (knowledgeBase: KnowledgeBaseRead) => {
    archiveKnowledgeBase.mutate(knowledgeBase.id, {
      onSuccess: () => {
        if (activeKnowledgeBaseId === knowledgeBase.id) {
          setActiveKnowledgeBaseId(null)
        }
      },
    })
  }

  const handleDelete = (knowledgeBase: KnowledgeBaseRead) => {
    if (!window.confirm(`删除空知识库「${knowledgeBase.name}」？`)) return
    deleteKnowledgeBase.mutate(knowledgeBase.id, {
      onSuccess: () => {
        if (activeKnowledgeBaseId === knowledgeBase.id) {
          setActiveKnowledgeBaseId(null)
        }
      },
    })
  }

  const renderRow = (knowledgeBase: KnowledgeBaseRead, archived = false) => {
    const isEditing = editingId === knowledgeBase.id
    return (
      <article className="list-row knowledge-base-row" key={knowledgeBase.id}>
        {isEditing ? (
          <div className="knowledge-base-edit-grid">
            <div>
              <label className="field-label" htmlFor={`kb-name-${knowledgeBase.id}`}>
                知识库名称
              </label>
              <input
                id={`kb-name-${knowledgeBase.id}`}
                onChange={(event) => setEditForm((current) => ({ ...current, name: event.target.value }))}
                value={editForm.name}
              />
            </div>
            <div>
              <label className="field-label" htmlFor={`kb-description-${knowledgeBase.id}`}>
                描述
              </label>
              <input
                id={`kb-description-${knowledgeBase.id}`}
                onChange={(event) => setEditForm((current) => ({ ...current, description: event.target.value }))}
                value={editForm.description}
              />
            </div>
          </div>
        ) : (
          <div>
            <div className="profile-title-row">
              <h3>{knowledgeBase.name}</h3>
              <span className="mode-pill">{archived ? '已归档' : knowledgeBase.is_default ? '默认' : '可用'}</span>
              {activeKnowledgeBaseId === knowledgeBase.id ? <span className="mode-pill">当前</span> : null}
            </div>
            {knowledgeBase.description ? <p>{knowledgeBase.description}</p> : <p>暂无描述。</p>}
          </div>
        )}
        <div className="memory-actions">
          {!archived && !isEditing ? (
            <button className="secondary" onClick={() => setActiveKnowledgeBaseId(knowledgeBase.id)} type="button">
              设为当前
            </button>
          ) : null}
          {!archived && !isEditing ? (
            <button className="secondary" onClick={() => startEdit(knowledgeBase)} type="button">
              重命名
            </button>
          ) : null}
          {isEditing ? (
            <button disabled={isMutating || !editForm.name.trim()} onClick={() => handleUpdate(knowledgeBase.id)} type="button">
              保存
            </button>
          ) : null}
          {isEditing ? (
            <button className="secondary" onClick={() => setEditingId(null)} type="button">
              取消
            </button>
          ) : null}
          {!archived && !knowledgeBase.is_default && !isEditing ? (
            <button className="secondary" disabled={isMutating} onClick={() => handleArchive(knowledgeBase)} type="button">
              归档
            </button>
          ) : null}
          {archived ? (
            <button disabled={isMutating} onClick={() => restoreKnowledgeBase.mutate(knowledgeBase.id)} type="button">
              恢复
            </button>
          ) : null}
          {!knowledgeBase.is_default && !isEditing ? (
            <button className="secondary danger" disabled={isMutating} onClick={() => handleDelete(knowledgeBase)} type="button">
              删除空知识库
            </button>
          ) : null}
        </div>
      </article>
    )
  }

  return (
    <section className="center-panel full-span" aria-label="知识库管理">
      <div className="panel-header">
        <div>
          <p className="eyebrow">资料范围</p>
          <h2>知识库</h2>
        </div>
        <span className="count-pill">{activeKnowledgeBases.length}</span>
      </div>

      <form className="knowledge-base-create" onSubmit={handleCreate}>
        <div>
          <label className="field-label" htmlFor="kb-create-name">
            知识库名称
          </label>
          <input
            id="kb-create-name"
            onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))}
            value={createForm.name}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="kb-create-description">
            描述
          </label>
          <input
            id="kb-create-description"
            onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
            value={createForm.description}
          />
        </div>
        <div className="action-row">
          <button disabled={isMutating || !createForm.name.trim()} type="submit">
            新建知识库
          </button>
        </div>
      </form>

      <div className="settings-grid knowledge-base-lists">
        <div className="settings-section">
          <h3>可用知识库</h3>
          <div className="stack-list">
            {activeKnowledgeBases.length === 0 ? <p>暂无可用知识库。</p> : null}
            {activeKnowledgeBases.map((knowledgeBase) => renderRow(knowledgeBase))}
          </div>
        </div>
        <div className="settings-section">
          <h3>已归档</h3>
          <div className="stack-list">
            {archivedKnowledgeBases.length === 0 ? <p>暂无归档知识库。</p> : null}
            {archivedKnowledgeBases.map((knowledgeBase) => renderRow(knowledgeBase, true))}
          </div>
        </div>
      </div>
    </section>
  )
}
