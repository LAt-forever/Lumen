import { describe, expect, it } from 'vitest'

import type { MemoryGraphRead, RelationStatus } from '../api/types'
import { collapseNode, mergeGraphs } from './mergeGraph'

const node = (id: number) => ({ id, text: `m${id}`, memory_type: 'fact', status: 'active' })
const edge = (id: number, s: number, t: number) => ({
  id,
  source_memory_id: s,
  target_memory_id: t,
  relation_type: 'related_to' as const,
  provenance: 'user',
  strength: 70,
  status: 'active' as RelationStatus,
})

const graph = (nodes: number[], edges: [number, number, number][]): MemoryGraphRead => ({
  center_memory_id: nodes[0] ?? 0,
  nodes: nodes.map(node),
  edges: edges.map(([id, s, t]) => edge(id, s, t)),
})

describe('mergeGraphs', () => {
  it('合并去重节点和边', () => {
    const base = graph([1, 2], [[10, 1, 2]])
    const incoming = graph([2, 3], [[10, 1, 2], [11, 2, 3]])
    const result = mergeGraphs(base, incoming)
    expect(result.nodes.map((n) => n.id).sort()).toEqual([1, 2, 3])
    expect(result.edges.map((e) => e.id).sort()).toEqual([10, 11])
  })
})

describe('collapseNode', () => {
  it('移除仅由该节点引入且不连接其他展开节点的邻居', () => {
    const current = graph([1, 2, 3], [[10, 1, 2], [11, 1, 3]])
    const expandedIds = new Set([1])
    const result = collapseNode(current, 1, expandedIds)
    expect(result.nodes.map((n) => n.id)).toEqual([1])
    expect(result.edges).toEqual([])
  })

  it('保留仍连接其他展开节点的邻居', () => {
    const current = graph([1, 2, 4], [[10, 1, 2], [12, 4, 2]])
    const expandedIds = new Set([1, 4])
    const result = collapseNode(current, 1, expandedIds)
    expect(result.nodes.map((n) => n.id).sort()).toEqual([1, 2, 4])
  })
})
