from service.core.knowledge import KnowledgeService
from service.core.llm import AnswerProvider, EvidenceMemory, EvidencePack, ExtractiveAnswerProvider
from service.core.memory import MemoryService
from service.repositories.conversations import ConversationRepository
from service.schemas import ChatRequest, ChatResponse, CitationRead, UsedMemoryRead


class ChatOrchestrator:
    def __init__(
        self,
        conversations: ConversationRepository,
        knowledge: KnowledgeService,
        memories: MemoryService,
        answer_provider: AnswerProvider | None = None,
    ):
        self.conversations = conversations
        self.knowledge = knowledge
        self.memories = memories
        self.answer_provider = answer_provider or ExtractiveAnswerProvider()

    def _retrieval_confidence(self, chunks: list, memories: list) -> str:
        if chunks:
            return "grounded"
        if memories:
            return "memory-only"
        return "weak"

    def ask(self, request: ChatRequest) -> ChatResponse:
        title = request.message[:60] or "New conversation"
        conversation = self.conversations.get_or_create(request.conversation_id, title)
        user_message = self.conversations.add_message(conversation.id, "user", request.message)

        chunks = self.knowledge.search(request.message, limit=4)
        memory_rows = self.memories.search(request.message, limit=4)
        evidence = EvidencePack(
            question=request.message,
            chunks=chunks,
            memories=[
                EvidenceMemory(id=memory.id, text=memory.text, memory_type=memory.memory_type)
                for memory in memory_rows
            ],
            retrieval_confidence=self._retrieval_confidence(chunks, memory_rows),
        )
        result = self.answer_provider.answer(evidence)

        assistant_message = self.conversations.add_message(conversation.id, "assistant", result.answer)
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
            answer=result.answer,
            citations=citations,
            memories=[UsedMemoryRead(id=memory.id, text=memory.text, memory_type=memory.memory_type) for memory in memory_rows],
            confidence=result.confidence,
            answer_mode=result.answer_mode,
            fallback_reason=result.fallback_reason,
        )
