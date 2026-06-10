import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import { useHubGraph, useMemories } from '../api/hooks'
import type { MemoryGraphRead } from '../api/types'
import { applyFilters, type GraphFilters } from '../graph/filterGraph'
import { collapseNode, mergeGraphs } from '../graph/mergeGraph'
import { ALL_MEMORY_TYPES, ALL_RELATION_TYPES, GraphFilterPanel } from './GraphFilterPanel'
import { GraphToolbar } from './GraphToolbar'
import { MemoryGraphCanvas } from './MemoryGraphCanvas'

const EMPTY_GRAPH: MemoryGraphRead = { center_memory_id: 0, nodes: [], edges: [] }
const MAX_VISIBLE_NODES = 200

export function MemoryGraphPanel() {
  const { data: memories = [] } = useMemories()
  const { data: hubGraph, isLoading, isError, refetch } = useHubGraph(5)

  const [graph, setGraph] = useState<MemoryGraphRead>(EMPTY_GRAPH)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [positions, setPositions] = useState<Record<number, { x: number; y: number }>>({})
  const [filters, setFilters] = useState<GraphFilters>({
    memoryTypes: new Set(ALL_MEMORY_TYPES),
    relationTypes: new Set(ALL_RELATION_TYPES),
    minStrength: 0,
  })

  useEffect(() => {
    if (hubGraph) {
      setGraph(hubGraph)
    }
  }, [hubGraph])

  const visibleGraph = useMemo(() => applyFilters(graph, filters), [graph, filters])

  const expandNode = async (id: number) => {
    try {
      const neighbors = await api.memoryGraph(id, 1)
      setGraph((prev) => mergeGraphs(prev, neighbors))
      setExpandedIds((prev) => new Set(prev).add(id))
    } catch {
      // 展开失败不破坏已有图
    }
  }

  const handleNodeDoubleClick = (id: number) => {
    if (expandedIds.has(id)) {
      setGraph((prev) => collapseNode(prev, id, expandedIds))
      setExpandedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } else {
      void expandNode(id)
    }
  }

  const handleJumpToMemory = (id: number) => {
    void expandNode(id)
    setSelectedId(id)
  }

  const handleReset = () => {
    setGraph(hubGraph ?? EMPTY_GRAPH)
    setExpandedIds(new Set())
    setSelectedId(null)
    setPositions({})
  }

  const selectedMemory = memories.find((m) => m.id === selectedId)

  return (
    <section className="center-panel full-span" aria-label="记忆图谱">
      <div className="panel-header">
        <h2>记忆图谱</h2>
      </div>

      <GraphToolbar memories={memories} onJumpToMemory={handleJumpToMemory} onReset={handleReset} />
      <GraphFilterPanel filters={filters} onChange={setFilters} />

      {isError ? (
        <div className="graph-error">
          <p>加载图谱失败。</p>
          <button type="button" onClick={() => refetch()}>
            重试
          </button>
        </div>
      ) : isLoading ? (
        <p>正在加载图谱…</p>
      ) : graph.nodes.length === 0 ? (
        <p>还没有记忆，去添加一些资料吧。</p>
      ) : (
        <>
          {visibleGraph.nodes.length > MAX_VISIBLE_NODES ? (
            <p className="helper-text">节点过多（{visibleGraph.nodes.length}），建议用过滤器收窄范围。</p>
          ) : null}
          <MemoryGraphCanvas
            graph={visibleGraph}
            expandedIds={expandedIds}
            selectedId={selectedId}
            prevPositions={positions}
            onNodeClick={setSelectedId}
            onNodeDoubleClick={handleNodeDoubleClick}
            onPositionsComputed={setPositions}
          />
        </>
      )}

      {selectedMemory ? (
        <div className="graph-node-detail">
          <h3>记忆详情</h3>
          <p>{selectedMemory.text}</p>
          <p className="helper-text">类型：{selectedMemory.memory_type}　双击节点可展开/收起关系</p>
        </div>
      ) : null}
    </section>
  )
}
