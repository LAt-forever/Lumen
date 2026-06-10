import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'

import type { MemoryGraphEdge, MemoryGraphNode } from '../api/types'

export type LayoutNode = MemoryGraphNode & { x: number; y: number }

type SimNode = SimulationNodeDatum & { id: number }
type SimLink = SimulationLinkDatum<SimNode> & { strength: number }

export type ComputeLayoutOptions = {
  width: number
  height: number
  iterations?: number
  initialPositions?: Record<number, { x: number; y: number }>
}

export function computeLayout(
  nodes: MemoryGraphNode[],
  edges: MemoryGraphEdge[],
  options: ComputeLayoutOptions,
): LayoutNode[] {
  if (nodes.length === 0) return []
  const { width, height, iterations = 120, initialPositions = {} } = options

  const simNodes: SimNode[] = nodes.map((n, index) => {
    const seed = initialPositions[n.id]
    return {
      id: n.id,
      x: seed?.x ?? width / 2 + Math.cos((index / nodes.length) * Math.PI * 2) * 80,
      y: seed?.y ?? height / 2 + Math.sin((index / nodes.length) * Math.PI * 2) * 80,
    }
  })

  const nodeById = new Map(simNodes.map((n) => [n.id, n]))
  const simLinks: SimLink[] = edges
    .filter((e) => nodeById.has(e.source_memory_id) && nodeById.has(e.target_memory_id))
    .map((e) => ({ source: e.source_memory_id, target: e.target_memory_id, strength: e.strength }))

  const simulation = forceSimulation(simNodes)
    .force('charge', forceManyBody().strength(-300).theta(0.9))
    .force(
      'link',
      forceLink<SimNode, SimLink>(simLinks)
        .id((d) => d.id)
        .distance((l) => 160 - (l.strength / 100) * 80)
        .strength(0.3),
    )
    .force('center', forceCenter(width / 2, height / 2))
    .force('collide', forceCollide(28))
    .stop()

  for (let i = 0; i < iterations; i++) {
    simulation.tick()
  }

  return nodes.map((n) => {
    const sim = nodeById.get(n.id)!
    const x = Number.isFinite(sim.x) ? (sim.x as number) : width / 2
    const y = Number.isFinite(sim.y) ? (sim.y as number) : height / 2
    return { ...n, x, y }
  })
}
