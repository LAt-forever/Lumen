import type { GraphFilters } from '../graph/filterGraph'

const memoryTypeLabels: Record<string, string> = {
  preference: '偏好',
  fact: '事实',
  project: '项目',
  relationship: '关系',
  goal: '目标',
  event: '事件',
  note: '笔记',
}

const relationTypeLabels: Record<string, string> = {
  related_to: '相关',
  part_of: '属于',
  caused_by: '导致',
  supports: '支持',
  contradicts: '矛盾',
}

type Props = {
  filters: GraphFilters
  onChange: (next: GraphFilters) => void
}

function toggle(set: Set<string>, key: string): Set<string> {
  const next = new Set(set)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  return next
}

export function GraphFilterPanel({ filters, onChange }: Props) {
  return (
    <div className="graph-filter-panel" aria-label="图谱过滤器">
      <fieldset>
        <legend>记忆类型</legend>
        {Object.keys(memoryTypeLabels).map((type) => (
          <label key={type} className="filter-checkbox">
            <input
              type="checkbox"
              checked={filters.memoryTypes.has(type)}
              onChange={() => onChange({ ...filters, memoryTypes: toggle(filters.memoryTypes, type) })}
            />
            {memoryTypeLabels[type]}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>关系类型</legend>
        {Object.keys(relationTypeLabels).map((type) => (
          <label key={type} className="filter-checkbox">
            <input
              type="checkbox"
              checked={filters.relationTypes.has(type)}
              onChange={() => onChange({ ...filters, relationTypes: toggle(filters.relationTypes, type) })}
            />
            {relationTypeLabels[type]}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>最小关系强度: {filters.minStrength}</legend>
        <input
          type="range"
          min={0}
          max={100}
          value={filters.minStrength}
          onChange={(e) => onChange({ ...filters, minStrength: Number(e.target.value) })}
        />
      </fieldset>
    </div>
  )
}

export const ALL_MEMORY_TYPES = Object.keys(memoryTypeLabels)
export const ALL_RELATION_TYPES = Object.keys(relationTypeLabels)
