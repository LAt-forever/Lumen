import { describe, expect, it } from 'vitest'

import type { MemoryGraphRead } from '../api/types'
import { applyFilters, type GraphFilters } from './filterGraph'

const fullGraph: MemoryGraphRead = {
  center_memory_id: 1,
  nodes: [
    { id: 1, text: 'a', memory_type: 'fact', status: 'active' },
    { id: 2, text: 'b', memory_type: 'goal', status: 'active' },
    { id: 3, text: 'c', memory_type: 'fact', status: 'active' },
  ],
  edges: [
    { id: 10, source_memory_id: 1, target_memory_id: 2, relation_type: 'related_to', provenance: 'user', strength: 80, status: 'active' },
    { id: 11, source_memory_id: 1, target_memory_id: 3, relation_type: 'supports', provenance: 'user', strength: 40, status: 'active' },
  ],
}

const allTypes = new Set(['fact', 'goal'])
const allRelations = new Set(['related_to', 'supports'])

describe('applyFilters', () => {
  it('默认全选 + 强度0：返回全集', () => {
    const filters: GraphFilters = { memoryTypes: allTypes, relationTypes: allRelations, minStrength: 0 }
    const result = applyFilters(fullGraph, filters)
    expect(result.nodes).toHaveLength(3)
    expect(result.edges).toHaveLength(2)
  })

  it('按记忆类型过滤：隐藏 goal 节点及其边', () => {
    const filters: GraphFilters = { memoryTypes: new Set(['fact']), relationTypes: allRelations, minStrength: 0 }
    const result = applyFilters(fullGraph, filters)
    expect(result.nodes.map((n) => n.id).sort()).toEqual([1, 3])
    expect(result.edges.map((e) => e.id)).toEqual([11])
  })

  it('按关系强度过滤：隐藏 strength<50 的边', () => {
    const filters: GraphFilters = { memoryTypes: allTypes, relationTypes: allRelations, minStrength: 50 }
    const result = applyFilters(fullGraph, filters)
    expect(result.edges.map((e) => e.id)).toEqual([10])
    expect(result.nodes).toHaveLength(3)
  })

  it('按关系类型过滤：只显示 related_to', () => {
    const filters: GraphFilters = { memoryTypes: allTypes, relationTypes: new Set(['related_to']), minStrength: 0 }
    const result = applyFilters(fullGraph, filters)
    expect(result.edges.map((e) => e.id)).toEqual([10])
  })
})
