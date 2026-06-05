from service.schemas import ChunkRead


class ExtractiveAnswerProvider:
    def answer(self, question: str, chunks: list[ChunkRead], memories: list[str]) -> tuple[str, str]:
        if chunks:
            source_bits = " ".join(chunk.text for chunk in chunks[:2])
            memory_bits = f" Relevant confirmed memories: {' '.join(memories)}" if memories else ""
            return f"Based on your sources, {source_bits}{memory_bits}", "grounded"
        if memories:
            return f"I found relevant confirmed memories: {' '.join(memories)}", "memory-only"
        return "I do not have enough evidence in Lumen yet. Add a source or confirm a relevant memory first.", "weak"
