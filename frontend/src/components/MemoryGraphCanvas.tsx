import { useEffect, useMemo } from 'react'
import {
  Background,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { MemoryGraphRead } from '../api/types'
import { computeLayout } from '../graph/useGraphLayout'
import { MemoryNode } from './MemoryNode'

const nodeTypes = { memory: MemoryNode }

type Props = {
  graph: MemoryGraphRead
  expandedIds: Set<number>
  selectedId: number | null
  prevPositions: Record<number, { x: number; y: number }>
  onNodeClick: (id: number) => void
  onNodeDoubleClick: (id: number) => void
  onPositionsComputed: (positions: Record<number, { x: number; y: number }>) => void
}

const WIDTH = 900
const HEIGHT = 520

export function MemoryGraphCanvas({
  graph,
  expandedIds,
  selectedId,
  prevPositions,
  onNodeClick,
  onNodeDoubleClick,
  onPositionsComputed,
}: Props) {
  const layoutNodes = useMemo(
    () =>
      computeLayout(graph.nodes, graph.edges, {
        width: WIDTH,
        height: HEIGHT,
        initialPositions: prevPositions,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [graph],
  )

  useEffect(() => {
    const positions: Record<number, { x: number; y: number }> = {}
    for (const n of layoutNodes) positions[n.id] = { x: n.x, y: n.y }
    onPositionsComputed(positions)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutNodes])

  const rfNodes: Node[] = layoutNodes.map((n) => ({
    id: String(n.id),
    type: 'memory',
    position: { x: n.x, y: n.y },
    data: {
      label: n.text,
      memoryType: n.memory_type,
      expanded: expandedIds.has(n.id),
      selected: selectedId === n.id,
    },
  }))

  const rfEdges: Edge[] = graph.edges.map((e) => ({
    id: String(e.id),
    source: String(e.source_memory_id),
    target: String(e.target_memory_id),
    label: e.relation_type,
    animated: false,
  }))

  return (
    <div style={{ width: '100%', height: HEIGHT }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onNodeClick(Number(node.id))}
        onNodeDoubleClick={(_, node) => onNodeDoubleClick(Number(node.id))}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  )
}
