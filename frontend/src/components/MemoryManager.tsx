import { useState } from 'react'

import { useDuplicateMemorySuggestions, useForgetMemory, useMemories, useMergeMemory, useUpdateMemory } from '../api/hooks'
import type { MemoryRead } from '../api/types'
import { formatMemoryType } from '../i18n'
import { OrganizationControls } from './OrganizationControls'

const memoryTypes = ['preference', 'fact', 'project', 'relationship', 'goal', 'event', 'note']

type EditState = {
  id: number
  text: string
  memory_type: string
}

export function MemoryManager() {
  const { data: memories = [] } = useMemories()
  const { data: duplicateSuggestions = [] } = useDuplicateMemorySuggestions()
  const updateMemory = useUpdateMemory()
  const forgetMemory = useForgetMemory()
  const mergeMemory = useMergeMemory()
  const [editing, setEditing] = useState<EditState>()
  const [mergeTargets, setMergeTargets] = useState<Record<number, number>>({})
  const isBusy = updateMemory.isPending || forgetMemory.isPending || mergeMemory.isPending

  const startEdit = (memory: MemoryRead) => {
    setEditing({ id: memory.id, text: memory.text, memory_type: memory.memory_type })
  }

  const saveEdit = () => {
    if (!editing) {
      return
    }
    updateMemory.mutate(
      { memoryId: editing.id, payload: { text: editing.text, memory_type: editing.memory_type } },
      { onSuccess: () => setEditing(undefined) },
    )
  }

  const mergeTargetFor = (memory: MemoryRead) => mergeTargets[memory.id] ?? memories.find((candidate) => candidate.id !== memory.id)?.id

  return (
    <section className="center-panel" aria-label="已确认记忆">
      <div className="panel-header">
        <h2>已确认记忆</h2>
        <span className="count-pill">{memories.length}</span>
      </div>
      {memories.length > 0 ? (
        <div className="stack-list">
          {memories.map((memory) => {
            const isEditing = editing?.id === memory.id
            const mergeTarget = mergeTargetFor(memory)
            return (
              <article className="list-row" key={memory.id}>
                {isEditing && editing ? (
                  <div className="form-stack">
                    <label className="field-label" htmlFor={`memory-text-${memory.id}`}>
                      记忆内容
                    </label>
                    <textarea
                      id={`memory-text-${memory.id}`}
                      onChange={(event) => setEditing({ ...editing, text: event.target.value })}
                      value={editing.text}
                    />
                    <label className="field-label" htmlFor={`memory-type-${memory.id}`}>
                      记忆类型
                    </label>
                    <select
                      id={`memory-type-${memory.id}`}
                      onChange={(event) => setEditing({ ...editing, memory_type: event.target.value })}
                      value={editing.memory_type}
                    >
                      {memoryTypes.map((type) => (
                        <option key={type} value={type}>
                          {formatMemoryType(type)}
                        </option>
                      ))}
                    </select>
                    <div className="memory-actions">
                      <button disabled={isBusy || !editing.text.trim()} onClick={saveEdit} type="button">
                        保存记忆
                      </button>
                      <button disabled={isBusy} onClick={() => setEditing(undefined)} type="button" className="secondary">
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <strong>{formatMemoryType(memory.memory_type)}</strong>
                    <p>{memory.text}</p>
                    <p>来源：{memory.provenance}</p>
                    <OrganizationControls targetType="memory" targetId={memory.id} label="记忆" />
                    <div className="memory-actions">
                      <button disabled={isBusy} onClick={() => startEdit(memory)} type="button">
                        编辑
                      </button>
                      <button disabled={isBusy} onClick={() => forgetMemory.mutate(memory.id)} type="button" className="secondary">
                        遗忘
                      </button>
                    </div>
                    {memories.length > 1 ? (
                      <div className="merge-row">
                        <label className="field-label" htmlFor={`merge-target-${memory.id}`}>
                          合并目标 {memory.id}
                        </label>
                        <select
                          id={`merge-target-${memory.id}`}
                          onChange={(event) => setMergeTargets({ ...mergeTargets, [memory.id]: Number(event.target.value) })}
                          value={mergeTarget}
                        >
                          {memories
                            .filter((candidate) => candidate.id !== memory.id)
                            .map((candidate) => (
                              <option key={candidate.id} value={candidate.id}>
                                #{candidate.id} {candidate.text}
                              </option>
                            ))}
                        </select>
                        <button
                          disabled={isBusy || !mergeTarget}
                          onClick={() => mergeTarget && mergeMemory.mutate({ memoryId: memory.id, targetMemoryId: mergeTarget })}
                          type="button"
                        >
                          合并到目标
                        </button>
                      </div>
                    ) : null}
                  </>
                )}
              </article>
            )
          })}
          {duplicateSuggestions.length > 0 ? (
            <article className="list-row">
              <strong>可能重复记忆</strong>
              {duplicateSuggestions.map((suggestion) => (
                <div className="merge-row" key={`${suggestion.source_memory_id}-${suggestion.target_memory_id}`}>
                  <p>
                    #{suggestion.source_memory_id} {suggestion.source_text}
                  </p>
                  <p>
                    #{suggestion.target_memory_id} {suggestion.target_text}
                  </p>
                  <p>相似度：{suggestion.overlap_score.toFixed(2)}</p>
                  <button
                    disabled={isBusy}
                    onClick={() =>
                      mergeMemory.mutate({
                        memoryId: suggestion.source_memory_id,
                        targetMemoryId: suggestion.target_memory_id,
                      })
                    }
                    type="button"
                  >
                    合并这组记忆
                  </button>
                </div>
              ))}
            </article>
          ) : null}
        </div>
      ) : (
        <p>暂无已确认记忆。</p>
      )}
    </section>
  )
}
