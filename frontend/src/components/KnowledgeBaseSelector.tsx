import { SlidersHorizontal } from 'lucide-react'

import { useKnowledgeBaseContext } from '../knowledgeBase/KnowledgeBaseContext'

type KnowledgeBaseSelectorProps = {
  onManage: () => void
}

export function KnowledgeBaseSelector({ onManage }: KnowledgeBaseSelectorProps) {
  const { activeKnowledgeBaseId, activeKnowledgeBases, isLoading, setActiveKnowledgeBaseId } = useKnowledgeBaseContext()

  return (
    <div className="knowledge-base-selector">
      <label className="field-label" htmlFor="knowledge-base-select">
        知识库
      </label>
      <div className="knowledge-base-control">
        <select
          disabled={isLoading || activeKnowledgeBases.length === 0}
          id="knowledge-base-select"
          onChange={(event) => setActiveKnowledgeBaseId(Number(event.target.value))}
          value={activeKnowledgeBaseId ?? ''}
        >
          {activeKnowledgeBases.length === 0 ? <option value="">无可用知识库</option> : null}
          {activeKnowledgeBases.map((knowledgeBase) => (
            <option key={knowledgeBase.id} value={knowledgeBase.id}>
              {knowledgeBase.name}
            </option>
          ))}
        </select>
        <button aria-label="管理知识库" className="icon-button" onClick={onManage} type="button">
          <SlidersHorizontal size={16} strokeWidth={1.9} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
