import { describe, expect, it } from 'vitest'

import type { MemoryGraphEdge, MemoryGraphNode } from '../api/types'
import { computeLayout } from './useGraphLayout'

const nodes: MemoryGraphNode[] = [
  { id: 1, text: 'a', memory_type: 'fact', status: 'active' },
  { id: 2, text: 'b', memory_type: 'goal', status: 'active' },
  { id: 3, text: 'c', memory_type: 'fact', status: 'active' },
]
const edges: MemoryGraphEdge[] = [
  { id: 10, source_memory_id: 1, target_memory_id: 2, relation_type: 'related_to', provenance: 'user', strength: 70, status: 'active' },
]

describe('computeLayout', () => {
  it('为每个节点产出有限的 x/y 坐标', () => {
    const result = computeLayout(nodes, edges, { width: 800, height: 600, iterations: 100 })
    expect(result).toHaveLength(3)
    for (const n of result) {
      expect(Number.isFinite(n.x)).toBe(true)
      expect(Number.isFinite(n.y)).toBe(true)
    }
  })

  it('保留已有节点的传入坐标作为初始值', () => {
    const seeded = computeLayout(nodes, edges, {
      width: 800,
      height: 600,
      iterations: 0,
      initialPositions: { 1: { x: 123, y: 456 } },
    })
    const n1 = seeded.find((n) => n.id === 1)!
    expect(n1.x).toBe(123)
    expect(n1.y).toBe(456)
  })

  it('空输入返回空数组', () => {
    expect(computeLayout([], [], { width: 800, height: 600, iterations: 10 })).toEqual([])
  })
})
