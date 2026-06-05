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
            suggestions.append(f"Review {len(pending)} pending memory candidate(s).")
        if not active:
            suggestions.append("Confirm a memory so Lumen can personalize future answers.")
        if not suggestions:
            suggestions.append("Ask Lumen a follow-up question using your confirmed memories.")
        return ReviewRead(
            sources_added=self.sources.list()[:5],
            memories_confirmed=active[:5],
            pending_memories=pending[:5],
            recent_questions=self.conversations.recent_user_questions(),
            suggested_actions=suggestions,
        )
