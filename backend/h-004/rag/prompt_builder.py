from typing import List, Dict, Optional


def build_rag_prompt(
    query: str,
    retrieved_chunks: List[dict],
    instructions: Optional[str] = None,
    answer_guidelines: Optional[str] = None,
    include_citations: bool = True,
) -> str:
    instr = instructions or (
        "You are a knowledgeable assistant. Use the provided context chunks to answer the question."
    )
    guidelines = answer_guidelines or (
        "Answer concisely and accurately. If the context does not contain the answer, say you don't know."
    )

    header = f"System instructions: {instr}\nGuidelines: {guidelines}\n"

    context_lines = []
    for i, ch in enumerate(retrieved_chunks, start=1):
        tag = f"[Chunk {i} | Source: {ch.get('source')} | Pos: {ch.get('position')} | Score: {round(ch.get('score', 0.0), 4)}]"
        context_lines.append(f"{tag}\n{ch.get('text','').strip()}\n")
    context_block = "\n".join(context_lines) if context_lines else "(No context available)"

    if include_citations:
        cite_note = "When possible, cite specific chunks in square brackets like [Chunk 1], [Chunk 2]."
    else:
        cite_note = ""

    prompt = (
        f"{header}\n"
        f"Context:\n"
        f"{context_block}\n\n"
        f"{cite_note}\n"
        f"Question: {query}\n"
        f"Answer:"
    )

    return prompt

