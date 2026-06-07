from service.repositories.conversations import ConversationRepository
from service.repositories.memories import MemoryRepository
from service.repositories.sources import SourceRepository
from service.schemas import ReviewRead


class ReviewService:
    def __init__(self, sources: SourceRepository, memories: MemoryRepository, conversations: ConversationRepository):
        self.sources = sources
        self.memories = memories
        self.conversations = conversations

    def recent(self) -> ReviewRead:
        pending = self.memories.pending_candidates()
        active = self.memories.active_memories()
        suggestions = []
        if pending:
            suggestions.append(f"处理 {len(pending)} 条待确认记忆。")
        if not active:
            suggestions.append("确认一条记忆，让 Lumen 在后续回答中更贴合你。")
        if not suggestions:
            suggestions.append("基于已确认的记忆继续追问 Lumen。")
        return ReviewRead(
            sources_added=self.sources.list()[:5],
            memories_confirmed=active[:5],
            pending_memories=pending[:5],
            recent_questions=self.conversations.recent_user_questions(),
            suggested_actions=suggestions,
        )
