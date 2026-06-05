from service.core.knowledge import KnowledgeService
from service.core.llm import ExtractiveAnswerProvider
from service.core.memory import MemoryService
from service.repositories.conversations import ConversationRepository
from service.schemas import ChatRequest, ChatResponse, CitationRead, UsedMemoryRead


class ChatOrchestrator:
    def __init__(
        self,
        conversations: ConversationRepository,
        knowledge: KnowledgeService,
        memories: MemoryService,
        answer_provider: ExtractiveAnswerProvider | None = None,
    ):
        self.conversations = conversations
        self.knowledge = knowledge
        self.memories = memories
        self.answer_provider = answer_provider or ExtractiveAnswerProvider()

    def ask(self, request: ChatRequest) -> ChatResponse:
        title = request.message[:60] or "New conversation"
        conversation = self.conversations.get_or_create(request.conversation_id, title)
        user_message = self.conversations.add_message(conversation.id, "user", request.message)

        chunks = self.knowledge.search(request.message, limit=4)
        memory_rows = self.memories.search(request.message, limit=4)
        answer, confidence = self.answer_provider.answer(request.message, chunks, [memory.text for memory in memory_rows])

        assistant_message = self.conversations.add_message(conversation.id, "assistant", answer)
        citations: list[CitationRead] = []
        for chunk in chunks[:3]:
            self.conversations.add_citation(assistant_message.id, chunk.source_id, chunk.id, chunk.text[:300])
            citations.append(
                CitationRead(
                    source_id=chunk.source_id,
                    source_title=chunk.source_title,
                    chunk_id=chunk.id,
                    quote=chunk.text[:300],
                )
            )

        self.memories.extract_candidates(request.message, source_kind="message", source_ref=str(user_message.id))

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            answer=answer,
            citations=citations,
            memories=[UsedMemoryRead(id=memory.id, text=memory.text, memory_type=memory.memory_type) for memory in memory_rows],
            confidence=confidence,
        )
