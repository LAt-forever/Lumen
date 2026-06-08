import json
from dataclasses import dataclass

from service.core.knowledge import KnowledgeService
from service.core.llm import (
    AnswerProvider,
    AnswerResult,
    ChatCompletionError,
    EvidenceMemory,
    EvidencePack,
    ExtractiveAnswerProvider,
)
from service.core.memory import MemoryService
from service.repositories.conversations import ConversationRepository
from service.schemas import ChatRequest, ChatResponse, ChunkRead, CitationRead, UsedMemoryRead


@dataclass(frozen=True)
class PreparedChat:
    conversation_id: int
    user_message_id: int
    chunks: list[ChunkRead]
    memory_rows: list
    evidence: EvidencePack


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
        prepared = self._prepare(request)
        result = self.answer_provider.answer(prepared.evidence)
        return self._finalize(prepared, result)

    def stream(self, request: ChatRequest):
        prepared = self._prepare(request)
        stream_answer = getattr(self.answer_provider, "stream_answer", None)
        if not callable(stream_answer):
            result = self.answer_provider.answer(prepared.evidence)
            response = self._finalize(prepared, result)
            yield self._sse("chunk", {"text": result.answer})
            yield self._sse("final", response.model_dump(mode="json"))
            return

        answer_parts: list[str] = []
        try:
            stream_result = stream_answer(prepared.evidence)
            for chunk in stream_result.chunks:
                answer_parts.append(chunk)
                yield self._sse("chunk", {"text": chunk})
        except ChatCompletionError:
            if answer_parts:
                raise
            result = self.answer_provider.answer(prepared.evidence)
            response = self._finalize(prepared, result)
            yield self._sse("chunk", {"text": result.answer})
            yield self._sse("final", response.model_dump(mode="json"))
            return

        answer = "".join(answer_parts).strip()
        if not answer:
            result = self.answer_provider.answer(prepared.evidence)
            response = self._finalize(prepared, result)
            yield self._sse("chunk", {"text": result.answer})
            yield self._sse("final", response.model_dump(mode="json"))
            return

        result = AnswerResult(
            answer=answer,
            confidence=stream_result.confidence,
            answer_mode=stream_result.answer_mode,
            fallback_reason=stream_result.fallback_reason,
        )
        response = self._finalize(prepared, result)
        yield self._sse("final", response.model_dump(mode="json"))

    def _prepare(self, request: ChatRequest) -> PreparedChat:
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
        return PreparedChat(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            chunks=chunks,
            memory_rows=memory_rows,
            evidence=evidence,
        )

    def _finalize(self, prepared: PreparedChat, result: AnswerResult) -> ChatResponse:
        assistant_message = self.conversations.add_message(prepared.conversation_id, "assistant", result.answer)
        citations: list[CitationRead] = []
        for chunk in prepared.chunks[:3]:
            self.conversations.add_citation(assistant_message.id, chunk.source_id, chunk.id, chunk.text[:300])
            citations.append(
                CitationRead(
                    source_id=chunk.source_id,
                    source_title=chunk.source_title,
                    chunk_id=chunk.id,
                    quote=chunk.text[:300],
                    matched_terms=chunk.matched_terms,
                    matched_date=chunk.matched_date,
                    match_reason=chunk.match_reason,
                )
            )

        self.memories.extract_candidates(
            prepared.evidence.question,
            source_kind="message",
            source_ref=str(prepared.user_message_id),
        )

        return ChatResponse(
            conversation_id=prepared.conversation_id,
            message_id=assistant_message.id,
            answer=result.answer,
            citations=citations,
            memories=[
                UsedMemoryRead(id=memory.id, text=memory.text, memory_type=memory.memory_type)
                for memory in prepared.memory_rows
            ],
            confidence=result.confidence,
            answer_mode=result.answer_mode,
            fallback_reason=result.fallback_reason,
        )

    def _sse(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
