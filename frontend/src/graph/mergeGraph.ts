import type { MemoryGraphEdge, MemoryGraphNode, MemoryGraphRead } from '../api/types'

export function mergeGraphs(base: MemoryGraphRead, incoming: MemoryGraphRead): MemoryGraphRead {
  const nodeMap = new Map<number, MemoryGraphNode>()
  for (const n of base.nodes) nodeMap.set(n.id, n)
  for (const n of incoming.nodes) nodeMap.set(n.id, n)

  const edgeMap = new Map<number, MemoryGraphEdge>()
  for (const e of base.edges) edgeMap.set(e.id, e)
  for (const e of incoming.edges) edgeMap.set(e.id, e)

  return {
    center_memory_id: base.center_memory_id,
    nodes: Array.from(nodeMap.values()),
    edges: Array.from(edgeMap.values()),
  }
}

export function collapseNode(
  current: MemoryGraphRead,
  collapseId: number,
  expandedIds: Set<number>,
): MemoryGraphRead {
  const remainingExpanded = new Set(expandedIds)
  remainingExpanded.delete(collapseId)

  const keep = new Set<number>([collapseId, ...remainingExpanded])

  for (const edge of current.edges) {
    const { source_memory_id: s, target_memory_id: t } = edge
    if (remainingExpanded.has(s)) keep.add(t)
    if (remainingExpanded.has(t)) keep.add(s)
  }

  const nodes = current.nodes.filter((n) => keep.has(n.id))
  const keptIds = new Set(nodes.map((n) => n.id))
  const edges = current.edges.filter(
    (e) => keptIds.has(e.source_memory_id) && keptIds.has(e.target_memory_id),
  )

  return { center_memory_id: current.center_memory_id, nodes, edges }
}
