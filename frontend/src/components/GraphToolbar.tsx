import type { MemoryRead } from '../api/types'

type Props = {
  memories: MemoryRead[]
  onJumpToMemory: (memoryId: number) => void
  onReset: () => void
}

export function GraphToolbar({ memories, onJumpToMemory, onReset }: Props) {
  return (
    <div className="graph-toolbar" aria-label="图谱工具栏">
      <label className="field-label" htmlFor="graph-search">
        跳转到记忆
      </label>
      <select
        id="graph-search"
        defaultValue=""
        onChange={(e) => {
          const id = Number(e.target.value)
          if (id) onJumpToMemory(id)
        }}
      >
        <option value="">选择一条记忆…</option>
        {memories.map((m) => (
          <option key={m.id} value={m.id}>
            #{m.id} {m.text.slice(0, 40)}
          </option>
        ))}
      </select>
      <button type="button" className="secondary" onClick={onReset}>
        重置视图
      </button>
    </div>
  )
}
