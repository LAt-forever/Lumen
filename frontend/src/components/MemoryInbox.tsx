import { useConfirmMemory, useIgnoreMemory, usePendingMemories } from '../api/hooks'
import { formatMemoryType } from '../i18n'

export function MemoryInbox() {
  const { data: pendingMemories = [] } = usePendingMemories()
  const confirmMemory = useConfirmMemory()
  const ignoreMemory = useIgnoreMemory()
  const isReviewing = confirmMemory.isPending || ignoreMemory.isPending

  return (
    <section className="side-panel">
      <div className="panel-header">
        <h2>记忆收件箱</h2>
        <span className="count-pill">{pendingMemories.length}</span>
      </div>
      {pendingMemories.length > 0 ? (
        <div className="stack-list">
          {pendingMemories.map((memory) => (
            <article className="list-row" key={memory.id}>
              <strong>{formatMemoryType(memory.memory_type)}</strong>
              <p>{memory.text}</p>
              <div className="memory-actions">
                <button disabled={isReviewing} onClick={() => confirmMemory.mutate(memory)} type="button">
                  确认
                </button>
                <button disabled={isReviewing} onClick={() => ignoreMemory.mutate(memory.id)} type="button" className="secondary">
                  忽略
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p>暂无待确认记忆。</p>
      )}
    </section>
  )
}
