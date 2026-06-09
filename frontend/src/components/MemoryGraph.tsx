import { useEffect, useMemo, useRef, useState } from 'react'

import type { MemoryGraphEdge, MemoryGraphRead } from '../api/types'

type SimulationNode = {
  id: number
  text: string
  memory_type: string
  status: string
  x: number
  y: number
  vx: number
  vy: number
}

type MemoryGraphProps = {
  graph: MemoryGraphRead
  width: number
  height: number
  onSelectNode: (memoryId: number) => void
}

const relationLabels: Record<string, string> = {
  related_to: '相关',
  part_of: '属于',
  caused_by: '导致',
  supports: '支持',
  contradicts: '矛盾',
  merged_into: '合并入',
}

function runForceLayout(
  nodes: SimulationNode[],
  edges: MemoryGraphEdge[],
  width: number,
  height: number,
  centerId: number,
  iterations = 120,
) {
  const centerX = width / 2
  const centerY = height / 2
  for (let i = 0; i < iterations; i++) {
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        const dx = nodes[a].x - nodes[b].x
        const dy = nodes[a].y - nodes[b].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = 2000 / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        nodes[a].vx += fx
        nodes[a].vy += fy
        nodes[b].vx -= fx
        nodes[b].vy -= fy
      }
    }
    for (const edge of edges) {
      const source = nodes.find((n) => n.id === edge.source_memory_id)
      const target = nodes.find((n) => n.id === edge.target_memory_id)
      if (!source || !target) continue
      const dx = target.x - source.x
      const dy = target.y - source.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (dist - 100) * 0.03
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      source.vx += fx
      source.vy += fy
      target.vx -= fx
      target.vy -= fy
    }
    for (const node of nodes) {
      const dx = centerX - node.x
      const dy = centerY - node.y
      node.vx += dx * 0.005
      node.vy += dy * 0.005
      node.vx *= 0.9
      node.vy *= 0.9
      node.x += node.vx
      node.y += node.vy
    }
  }
  const center = nodes.find((n) => n.id === centerId)
  if (center) {
    center.x = centerX
    center.y = centerY
  }
}

export function MemoryGraph({ graph, width, height, onSelectNode }: MemoryGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [hoverEdge, setHoverEdge] = useState<number | null>(null)

  const nodes = useMemo<SimulationNode[]>(() => {
    const centerX = width / 2
    const centerY = height / 2
    return graph.nodes.map((node, index) => ({
      ...node,
      x: centerX + Math.cos((index / Math.max(1, graph.nodes.length)) * Math.PI * 2) * 80,
      y: centerY + Math.sin((index / Math.max(1, graph.nodes.length)) * Math.PI * 2) * 80,
      vx: 0,
      vy: 0,
    }))
  }, [graph, width, height])

  useEffect(() => {
    runForceLayout(nodes, graph.edges, width, height, graph.center_memory_id)
    if (svgRef.current) {
      svgRef.current.setAttribute('viewBox', `0 0 ${width} ${height}`)
    }
  }, [nodes, graph.edges, graph.center_memory_id, width, height])

  return (
    <svg ref={svgRef} className="memory-graph" width={width} height={height} role="img" aria-label="记忆关系图">
      {graph.edges.map((edge) => {
        const source = nodes.find((n) => n.id === edge.source_memory_id)
        const target = nodes.find((n) => n.id === edge.target_memory_id)
        if (!source || !target) return null
        const midX = (source.x + target.x) / 2
        const midY = (source.y + target.y) / 2
        return (
          <g key={edge.id} onMouseEnter={() => setHoverEdge(edge.id)} onMouseLeave={() => setHoverEdge(null)}>
            <line
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              className={`memory-graph-edge ${edge.relation_type}`}
              markerEnd="url(#arrowhead)"
            />
            {hoverEdge === edge.id ? (
              <g>
                <rect x={midX - 40} y={midY - 14} width={80} height={20} rx={4} className="memory-graph-tooltip-bg" />
                <text x={midX} y={midY} className="memory-graph-tooltip-text" textAnchor="middle" dominantBaseline="middle">
                  {relationLabels[edge.relation_type] ?? edge.relation_type} · {edge.strength}
                </text>
              </g>
            ) : null}
          </g>
        )
      })}
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="#8aa89c" />
        </marker>
      </defs>
      {nodes.map((node) => {
        const isCenter = node.id === graph.center_memory_id
        return (
          <g
            key={node.id}
            className={`memory-graph-node ${isCenter ? 'center' : ''}`}
            onClick={() => onSelectNode(node.id)}
            style={{ cursor: 'pointer' }}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={isCenter ? 18 : 12}
              className={`memory-graph-node-circle ${node.memory_type}`}
            />
            <text x={node.x} y={node.y + (isCenter ? 32 : 24)} className="memory-graph-node-label" textAnchor="middle">
              {node.text.length > 20 ? `${node.text.slice(0, 20)}...` : node.text}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
