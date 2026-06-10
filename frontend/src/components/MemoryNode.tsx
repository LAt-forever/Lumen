import { Handle, Position } from '@xyflow/react'

export type MemoryNodeData = {
  label: string
  memoryType: string
  expanded: boolean
  selected: boolean
}

const typeColors: Record<string, string> = {
  preference: '#8b5cf6',
  fact: '#3b82f6',
  project: '#f59e0b',
  relationship: '#ec4899',
  goal: '#10b981',
  event: '#06b6d4',
  note: '#6b7280',
}

export function MemoryNode({ data }: { data: MemoryNodeData }) {
  const color = typeColors[data.memoryType] ?? '#6b7280'
  return (
    <div
      className="memory-node"
      style={{
        background: color,
        border: data.selected ? '3px solid #111' : data.expanded ? '2px solid #fff' : '2px dashed #fff',
        borderRadius: 10,
        padding: '6px 10px',
        color: '#fff',
        fontSize: 12,
        maxWidth: 160,
        cursor: 'pointer',
      }}
      title={data.label}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <span>{data.label.length > 20 ? `${data.label.slice(0, 20)}…` : data.label}</span>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  )
}
