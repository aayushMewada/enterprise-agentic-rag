SYSTEM_PROMPT = (
    "You are an interview-prep assistant for job interview experiences. "
    "Answer the user question using ONLY the context provided below. "
    "When useful, organize answers by company, year, interview round, "
    "topics asked, difficulty, outcome, and preparation advice. "
    "For preparation questions, summarize common rounds, technical topics, "
    "aptitude or coding areas, HR or behavioral themes, example questions, "
    "and practical preparation tips. "
    "If the answer is not in the context, say "
    "\"I don't have enough information to answer that.\" "
    "Do not make up information. "
    "Every factual bullet or paragraph must include context citations "
    "using labels such as [1] or [2]."
)


def build_prompt(question: str, chunks: list[dict]) -> list[dict]:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f'[{i}] {_format_source(chunk)}\n{chunk["text"]}'
        )

    context = "\n\n".join(context_parts)
    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def _format_source(chunk: dict) -> str:
    source = f'Source: {chunk["source"]}'
    page = chunk.get("page_start")

    if page is None:
        return source

    return f"{source}, page {page}"
