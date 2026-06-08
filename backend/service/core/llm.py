from dataclasses import dataclass, replace
from typing import Protocol

from service.config import Settings
from service.schemas import ChunkRead


@dataclass(frozen=True)
class EvidenceMemory:
    id: int
    text: str
    memory_type: str


@dataclass(frozen=True)
class EvidencePack:
    question: str
    chunks: list[ChunkRead]
    memories: list[EvidenceMemory]
    retrieval_confidence: str

    @property
    def has_evidence(self) -> bool:
        return bool(self.chunks or self.memories)


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    confidence: str
    answer_mode: str
    fallback_reason: str | None = None


class AnswerProvider(Protocol):
    def answer(self, evidence: EvidencePack) -> AnswerResult:
        ...


class ExtractiveAnswerProvider:
    def answer(self, evidence: EvidencePack) -> AnswerResult:
        memories = [memory.text for memory in evidence.memories]
        if evidence.chunks:
            source_bits = " ".join(chunk.text for chunk in evidence.chunks[:2])
            memory_bits = f" 已确认记忆：{' '.join(memories)}" if memories else ""
            return AnswerResult(
                answer=f"根据你的资料，{source_bits}{memory_bits}",
                confidence="grounded",
                answer_mode="extractive",
            )
        if memories:
            return AnswerResult(
                answer=f"我找到了相关的已确认记忆：{' '.join(memories)}",
                confidence="memory-only",
                answer_mode="extractive",
            )
        return AnswerResult(
            answer="Lumen 里还没有足够证据。请先添加相关资料，或确认一条相关记忆。",
            confidence="weak",
            answer_mode="extractive",
        )


class FallbackAnswerProvider:
    def __init__(self, fallback: AnswerProvider, reason: str):
        self.fallback = fallback
        self.reason = reason

    def answer(self, evidence: EvidencePack) -> AnswerResult:
        result = self.fallback.answer(evidence)
        return replace(result, fallback_reason=self.reason)


def build_answer_provider(settings: Settings) -> AnswerProvider:
    fallback = ExtractiveAnswerProvider()
    if settings.llm_mode != "llm":
        return fallback
    if not settings.llm_api_key or not settings.llm_model:
        return FallbackAnswerProvider(fallback, "LLM 未配置，已使用摘录模式。")
    return fallback
