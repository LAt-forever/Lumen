from service.schemas import ChunkRead


class ExtractiveAnswerProvider:
    def answer(self, question: str, chunks: list[ChunkRead], memories: list[str]) -> tuple[str, str]:
        if chunks:
            source_bits = " ".join(chunk.text for chunk in chunks[:2])
            memory_bits = f" 已确认记忆：{' '.join(memories)}" if memories else ""
            return f"根据你的资料，{source_bits}{memory_bits}", "grounded"
        if memories:
            return f"我找到了相关的已确认记忆：{' '.join(memories)}", "memory-only"
        return "Lumen 里还没有足够证据。请先添加相关资料，或确认一条相关记忆。", "weak"
