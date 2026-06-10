import { describe, expect, it } from 'vitest'

import { applyFilters, type GraphFilters } from '../graph/filterGraph'
import type { MemoryGraphRead } from '../api/types'

// MemoryGraph 组件已被 MemoryGraphCanvas 替代。画布渲染依赖真实 DOM 尺寸，
// 单测聚焦在已拆分的纯函数 (mergeGraph/filterGraph/useGraphLayout)。
// 这里保留一个 smoke 测试确认过滤集成。

describe('graph filtering integration', () => {
  it('全选过滤器返回全部节点', () => {
    const graph: MemoryGraphRead = {
      center_memory_id: 1,
      nodes: [{ id: 1, text: 'a', memory_type: 'fact', status: 'active' }],
      edges: [],
    }
    const filters: GraphFilters = {
      memoryTypes: new Set(['fact']),
      relationTypes: new Set(['related_to']),
      minStrength: 0,
    }
    expect(applyFilters(graph, filters).nodes).toHaveLength(1)
  })
})
