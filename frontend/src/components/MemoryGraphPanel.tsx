import { useMemo, useState } from 'react'

import { useCreateMemoryRelation, useForgetMemoryRelation, useMemories, useMemoryGraph, useMemoryRelations } from '../api/hooks'
import type { MemoryRelationCreate, RelationType } from '../api/types'
import { formatMemoryType } from '../i18n'
import { MemoryGraph } from './MemoryGraph'

const relationTypes: RelationType[] = ['related_to', 'part_of', 'caused_by', 'supports', 'contradicts']

const relationLabels: Record<string, string> = {
  related_to: '相关',
  part_of: '属于',
  caused_by: '导致',
  supports: '支持',
  contradicts: '矛盾',
}

export function MemoryGraphPanel() {
  const { data: memories = [] } = useMemories()
  const [centerId, setCenterId] = useState<number | undefined>(memories[0]?.id)
  const [depth, setDepth] = useState<1 | 2 | 3>(2)
  const { data: graph } = useMemoryGraph(centerId, depth)
  const { data: relations = [] } = useMemoryRelations(centerId)
  const createRelation = useCreateMemoryRelation()
  const forgetRelation = useForgetMemoryRelation()

  const [targetId, setTargetId] = useState<number | undefined>(undefined)
  const [relationType, setRelationType] = useState<RelationType>('related_to')
  const [strength, setStrength] = useState<number>(70)

  const eligibleTargets = useMemo(
    () => memories.filter((memory) => memory.id !== centerId),
    [memories, centerId],
  )

  const handleAddRelation = () => {
    if (centerId == null || targetId == null) return
    const payload: MemoryRelationCreate = {
      target_memory_id: targetId,
      relation_type: relationType,
      provenance: 'user',
      strength,
    }
    createRelation.mutate(
      { memoryId: centerId, payload },
      {
        onSuccess: () => {
          setTargetId(undefined)
          setStrength(70)
        },
      },
    )
  }

  return (
    <section className="center-panel full-span" aria-label="记忆图谱">
      <div className="panel-header">
        <h2>记忆图谱</h2>
      </div>

      <div className="graph-controls">
        <label className="field-label" htmlFor="center-memory">
          中心记忆
        </label>
        <select id="center-memory" value={centerId ?? ''} onChange={(event) => setCenterId(Number(event.target.value))}>
          {memories.map((memory) => (
            <option key={memory.id} value={memory.id}>
              #{memory.id} {formatMemoryType(memory.memory_type)} · {memory.text.slice(0, 40)}
            </option>
          ))}
        </select>

        <label className="field-label" htmlFor="graph-depth">
          探索深度
        </label>
        <select
          id="graph-depth"
          value={depth}
          onChange={(event) => setDepth(Number(event.target.value) as 1 | 2 | 3)}
        >
          <option value={1}>1 层</option>
          <option value={2}>2 层</option>
          <option value={3}>3 层</option>
        </select>
      </div>

      {graph ? (
        <MemoryGraph graph={graph} width={800} height={420} onSelectNode={(id) => setCenterId(id)} />
      ) : (
        <p>请选择一条记忆作为图谱中心。</p>
      )}

      {centerId != null ? (
        <div className="graph-relation-editor">
          <h3>添加关系</h3>
          <div className="inline-fields">
            <select value={targetId ?? ''} onChange={(event) => setTargetId(Number(event.target.value))}>
              <option value="">选择目标记忆</option>
              {eligibleTargets.map((memory) => (
                <option key={memory.id} value={memory.id}>
                  #{memory.id} {memory.text.slice(0, 40)}
                </option>
              ))}
            </select>
            <select value={relationType} onChange={(event) => setRelationType(event.target.value as RelationType)}>
              {relationTypes.map((type) => (
                <option key={type} value={type}>
                  {relationLabels[type]}
                </option>
              ))}
            </select>
          </div>
          <label className="field-label" htmlFor="relation-strength">
            强度: {strength}
          </label>
          <input
            id="relation-strength"
            type="range"
            min={0}
            max={100}
            value={strength}
            onChange={(event) => setStrength(Number(event.target.value))}
          />
          <div className="memory-actions">
            <button disabled={targetId == null || createRelation.isPending} onClick={handleAddRelation} type="button">
              添加关系
            </button>
          </div>

          {relations.length > 0 ? (
            <>
              <h3>当前关系</h3>
              <ul className="plain-list">
                {relations.map((relation) => (
                  <li key={relation.id}>
                    {relation.source_memory_id === centerId ? '→' : '←'} #
                    {relation.source_memory_id === centerId ? relation.target_memory_id : relation.source_memory_id}{' '}
                    {relationLabels[relation.relation_type] ?? relation.relation_type} · 强度 {relation.strength}
                    <button
                      disabled={forgetRelation.isPending}
                      onClick={() => forgetRelation.mutate({ memoryId: centerId, relationId: relation.id })}
                      type="button"
                      className="secondary"
                    >
                      遗忘
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
