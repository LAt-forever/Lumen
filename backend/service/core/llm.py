from dataclasses import dataclass, replace
from typing import Protocol
from urllib.parse import urljoin

import httpx

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


class ChatCompletionClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        ...


class HttpxChatCompletionClient:
    def __init__(self, base_url: str, model: str, api_key: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/") + "/"
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = httpx.post(
            urljoin(self.base_url, "chat/completions"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty chat completion content")
        return content.strip()


class OpenAICompatibleAnswerProvider:
    def __init__(
        self,
        client: ChatCompletionClient,
        fallback_provider: AnswerProvider,
        fallback_enabled: bool,
    ):
        self.client = client
        self.fallback_provider = fallback_provider
        self.fallback_enabled = fallback_enabled

    def answer(self, evidence: EvidencePack) -> AnswerResult:
        if not evidence.has_evidence:
            result = self.fallback_provider.answer(evidence)
            return replace(result, fallback_reason="证据不足，已使用摘录模式。")
        try:
            answer = self.client.complete(self._messages(evidence))
        except Exception:
            if not self.fallback_enabled:
                raise
            result = self.fallback_provider.answer(evidence)
            return replace(result, fallback_reason="LLM 请求失败，已使用摘录模式。")
        return AnswerResult(
            answer=answer,
            confidence=evidence.retrieval_confidence,
            answer_mode="llm",
        )

    def _messages(self, evidence: EvidencePack) -> list[dict[str, str]]:
        system = (
            "你是 Lumen，一个本地优先的个人知识库助手。"
            "只能依据用户提供的资料片段和已确认记忆回答。"
            "如果证据不足，请明确说明不知道，不要编造事实、日期、来源或用户偏好。"
            "用简洁中文回答。"
        )
        source_lines = [
            f"[资料 {index} | source_id={chunk.source_id} | chunk_id={chunk.id} | {chunk.source_title}]\n{chunk.text}"
            for index, chunk in enumerate(evidence.chunks, start=1)
        ]
        memory_lines = [
            f"[记忆 {memory.id} | {memory.memory_type}] {memory.text}"
            for memory in evidence.memories
        ]
        user = (
            f"问题：{evidence.question}\n\n"
            "可用资料：\n"
            f"{chr(10).join(source_lines) if source_lines else '无'}\n\n"
            "已确认记忆：\n"
            f"{chr(10).join(memory_lines) if memory_lines else '无'}\n\n"
            "请只基于以上证据回答。"
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_answer_provider(settings: Settings) -> AnswerProvider:
    fallback = ExtractiveAnswerProvider()
    if settings.llm_mode != "llm":
        return fallback
    if not settings.llm_api_key or not settings.llm_model:
        return FallbackAnswerProvider(fallback, "LLM 未配置，已使用摘录模式。")
    client = HttpxChatCompletionClient(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return OpenAICompatibleAnswerProvider(
        client=client,
        fallback_provider=fallback,
        fallback_enabled=settings.llm_fallback_enabled,
    )
