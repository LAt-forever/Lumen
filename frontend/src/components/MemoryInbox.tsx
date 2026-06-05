import { useConfirmMemory, useIgnoreMemory, usePendingMemories } from '../api/hooks'

export function MemoryInbox() {
  const { data: pendingMemories = [] } = usePendingMemories()
  const confirmMemory = useConfirmMemory()
  const ignoreMemory = useIgnoreMemory()
  const isReviewing = confirmMemory.isPending || ignoreMemory.isPending

  return (
    <section className="side-panel">
      <div className="panel-header">
        <h2>Memory Inbox</h2>
        <span className="count-pill">{pendingMemories.length}</span>
      </div>
      {pendingMemories.length > 0 ? (
        <div className="stack-list">
          {pendingMemories.map((memory) => (
            <article className="list-row" key={memory.id}>
              <strong>{memory.memory_type}</strong>
              <p>{memory.text}</p>
              <div className="memory-actions">
                <button disabled={isReviewing} onClick={() => confirmMemory.mutate(memory)} type="button">
                  Confirm
                </button>
                <button disabled={isReviewing} onClick={() => ignoreMemory.mutate(memory.id)} type="button" className="secondary">
                  Ignore
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p>No pending memories yet.</p>
      )}
    </section>
  )
}
