import type { MemoryGraphRead } from '../api/types'

export type GraphFilters = {
  memoryTypes: Set<string>
  relationTypes: Set<string>
  minStrength: number
}

export function applyFilters(graph: MemoryGraphRead, filters: GraphFilters): MemoryGraphRead {
  const nodes = graph.nodes.filter((n) => filters.memoryTypes.has(n.memory_type))
  const visibleNodeIds = new Set(nodes.map((n) => n.id))

  const edges = graph.edges.filter(
    (e) =>
      filters.relationTypes.has(e.relation_type) &&
      e.strength >= filters.minStrength &&
      visibleNodeIds.has(e.source_memory_id) &&
      visibleNodeIds.has(e.target_memory_id),
  )

  return { center_memory_id: graph.center_memory_id, nodes, edges }
}
